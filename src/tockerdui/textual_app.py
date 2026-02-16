"""Textual-based UI for tockerdui."""

from __future__ import annotations

import subprocess
import time
from typing import Any, Optional

from textual import events
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Footer, Header, Input, Static
from rich.markup import escape as rich_escape

from .backend import DockerBackend
from .config import config_manager
from .stats import StatsCollector


class ConfirmScreen(ModalScreen[bool]):
    def __init__(self, question: str) -> None:
        super().__init__()
        self.question = question

    def compose(self) -> ComposeResult:
        yield Vertical(
            Static("Confirm", classes="modal_title"),
            Static(self.question, classes="modal_body"),
            Static("[Enter/Y] Yes    [Esc/N] No", classes="modal_hint"),
            id="modal",
        )

    async def on_key(self, event: events.Key) -> None:
        if event.key in ("enter", "y", "Y"):
            self.dismiss(True)
        elif event.key in ("escape", "n", "N"):
            self.dismiss(False)


class InputScreen(ModalScreen[Optional[str]]):
    def __init__(self, prompt: str) -> None:
        super().__init__()
        self.prompt = prompt

    def compose(self) -> ComposeResult:
        yield Vertical(
            Static("Input", classes="modal_title"),
            Static(self.prompt, classes="modal_body"),
            Input(placeholder="Type value and press Enter", id="input_value"),
            Static("[Esc] Cancel", classes="modal_hint"),
            id="modal",
        )

    def on_mount(self) -> None:
        self.query_one("#input_value", Input).focus()

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        value = event.value.strip()
        self.dismiss(value or None)

    async def on_key(self, event: events.Key) -> None:
        if event.key == "escape":
            self.dismiss(None)


class ActionMenuScreen(ModalScreen[Optional[str]]):
    def __init__(self, title: str, options: list[tuple[str, str]]) -> None:
        super().__init__()
        self.title = title
        self.options = options
        self.index = 0

    def compose(self) -> ComposeResult:
        yield Vertical(
            Static(self.title, classes="modal_title"),
            Static("", id="menu_options", classes="modal_body"),
            Static("[Up/Down] Move  [Enter] Select  [Esc] Cancel", classes="modal_hint"),
            id="modal",
        )

    def on_mount(self) -> None:
        self._render()

    def _render(self) -> None:
        lines = []
        for idx, (label, key) in enumerate(self.options):
            marker = ">" if idx == self.index else " "
            lines.append(f"{marker} {label} ({key})")
        self.query_one("#menu_options", Static).update("\n".join(lines))

    async def on_key(self, event: events.Key) -> None:
        if event.key == "up":
            self.index = (self.index - 1) % len(self.options)
            self._render()
        elif event.key == "down":
            self.index = (self.index + 1) % len(self.options)
            self._render()
        elif event.key == "enter":
            self.dismiss(self.options[self.index][1])
        elif event.key == "escape":
            self.dismiss(None)


class TockerTextualApp(App[None]):
    TITLE = "tockerdui"
    SUB_TITLE = "Docker TUI"

    CSS = """
    Screen {
      layout: vertical;
    }

    #tabs {
      height: 1;
      padding: 0 1;
      background: $surface;
      color: $text;
    }

    #main {
      height: 1fr;
    }

    #list {
      width: 58%;
      border: round $accent;
      padding: 0 1;
      overflow: auto;
    }

    #details {
      width: 42%;
      border: round $accent;
      padding: 0 1;
      overflow: auto;
    }

    #status {
      height: 1;
      padding: 0 1;
      background: $panel;
      color: $text;
    }

    #modal {
      width: 70;
      height: auto;
      border: round $accent;
      background: $surface;
      padding: 1 2;
      align: center middle;
    }

    .modal_title {
      text-style: bold;
      margin-bottom: 1;
    }

    .modal_body {
      margin-bottom: 1;
    }

    .modal_hint {
      color: $text-muted;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("1", "tab_containers", "Containers"),
        Binding("2", "tab_images", "Images"),
        Binding("3", "tab_volumes", "Volumes"),
        Binding("4", "tab_networks", "Networks"),
        Binding("5", "tab_compose", "Compose"),
        Binding("6", "tab_stats", "Stats"),
        Binding("up", "up", "Up"),
        Binding("down", "down", "Down"),
        Binding("pageup", "page_up", "Page Up"),
        Binding("pagedown", "page_down", "Page Down"),
        Binding("enter", "open_menu", "Actions"),
        Binding("/", "start_filter", "Filter"),
        Binding("b", "toggle_bulk", "Bulk"),
        Binding("space", "toggle_select", "Select"),
        Binding("a", "select_all", "Select All"),
        Binding("d", "select_none", "Select None"),
        Binding("escape", "clear_filter", "Clear Filter"),
        Binding("S", "cycle_sort", "Sort"),
    ]

    TABS = ["containers", "images", "volumes", "networks", "compose", "stats"]

    def __init__(self) -> None:
        super().__init__()
        self.backend = DockerBackend()
        self.selected_tab = "containers"
        self.selected_index = 0
        self.scroll_offset = 0
        self.filter_text = ""
        self.is_filtering = False
        self.bulk_select_mode = False
        self.message = ""
        self.sort_mode = "name"
        self.focused_pane = "list"

        self.containers: list[Any] = []
        self.images: list[Any] = []
        self.volumes: list[Any] = []
        self.networks: list[Any] = []
        self.composes: list[Any] = []
        self.logs: list[str] = []
        self.self_usage = ""

        self.bulk_selected: dict[str, set[str]] = {
            "containers": set(),
            "images": set(),
            "volumes": set(),
            "networks": set(),
            "compose": set(),
        }

        self._last_containers = 0.0
        self._last_others = 0.0

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Static("", id="tabs")
        yield Horizontal(
            Static("", id="list"),
            Static("", id="details"),
            id="main",
        )
        yield Static("", id="status")
        yield Footer()

    def on_mount(self) -> None:
        self.set_interval(0.25, self._tick)
        self._refresh_all(force=True)
        self._render()

    def _get_tab_items(self, tab: Optional[str] = None) -> list[Any]:
        tab = tab or self.selected_tab
        if tab == "containers":
            items = list(self.containers)
            if self.sort_mode == "name":
                items.sort(key=lambda x: x.name)
            elif self.sort_mode == "status":
                items.sort(key=lambda x: x.status)
            elif self.sort_mode == "cpu":
                def get_cpu(c: Any) -> float:
                    try:
                        return float(str(c.cpu_percent).strip("%"))
                    except Exception:
                        return -1.0
                items.sort(key=get_cpu, reverse=True)
        elif tab == "images":
            items = sorted(self.images, key=lambda x: x.short_id)
        elif tab == "volumes":
            items = sorted(self.volumes, key=lambda x: x.name)
        elif tab == "networks":
            items = sorted(self.networks, key=lambda x: x.name)
        elif tab == "compose":
            items = sorted(self.composes, key=lambda x: x.name)
        else:
            items = []

        if not self.filter_text:
            return items

        f = self.filter_text.lower()
        filtered: list[Any] = []
        for item in items:
            if tab == "containers" and (f in item.name.lower() or f in item.image.lower()):
                filtered.append(item)
            elif tab == "images" and (f in item.short_id.lower() or any(f in t.lower() for t in item.tags)):
                filtered.append(item)
            elif tab in ("volumes", "networks", "compose") and f in item.name.lower():
                filtered.append(item)
        return filtered

    def _item_id(self, tab: str, item: Any) -> str:
        if tab in ("containers", "images", "networks"):
            return item.id
        return item.name

    def _selected_item(self) -> Optional[Any]:
        items = self._get_tab_items()
        if 0 <= self.selected_index < len(items):
            return items[self.selected_index]
        return None

    def _normalize_selection(self) -> None:
        items = self._get_tab_items()
        if not items:
            self.selected_index = 0
            self.scroll_offset = 0
            return
        self.selected_index = max(0, min(self.selected_index, len(items) - 1))

    def _refresh_all(self, force: bool = False) -> None:
        now = time.monotonic()

        if force or now - self._last_containers >= 1.0:
            self.containers = self.backend.get_containers()
            self.self_usage = self.backend.get_self_usage()
            self._last_containers = now

        if force or now - self._last_others >= 5.0:
            self.images = self.backend.get_images()
            self.volumes = self.backend.get_volumes()
            self.networks = self.backend.get_networks()
            self.composes = self.backend.get_composes()
            self._last_others = now

        if self.selected_tab == "containers":
            selected = self._selected_item()
            if selected:
                self.logs = self.backend.get_logs(selected.id, tail=100)

        self._normalize_selection()

    def _set_message(self, message: str) -> None:
        self.message = message

    def _format_tabs(self) -> str:
        labels = []
        for idx, tab in enumerate(self.TABS, start=1):
            label = tab.upper()
            if tab == self.selected_tab:
                labels.append(f"[{idx}:{label}]")
            else:
                labels.append(f" {idx}:{label} ")
        return " ".join(labels)

    def _row(self, tab: str, item: Any) -> str:
        if tab == "containers":
            cpu = getattr(item, "cpu_percent", "--")
            ram = getattr(item, "ram_usage", "--")
            return f"{item.project[:12]:12} {item.name[:20]:20} {item.status[:10]:10} {str(cpu):7} {str(ram):10} {item.image[:28]}"
        if tab == "images":
            return f"{item.short_id[:15]:15} {item.size_mb:8.1f}MB {item.created[:10]:10} {str(item.tags)[:45]}"
        if tab == "volumes":
            return f"{item.name[:20]:20} {item.driver[:10]:10} {item.mountpoint[:45]}"
        if tab == "networks":
            return f"{item.name[:20]:20} {item.driver[:10]:10} {item.subnet[:40]}"
        if tab == "compose":
            return f"{item.name[:20]:20} {item.status[:10]:10} {item.config_files[:45]}"
        return ""

    def _header(self, tab: str) -> str:
        if tab == "containers":
            return "PROJECT      NAME                 STATUS     CPU     MEM        IMAGE"
        if tab == "images":
            return "SHORT ID        SIZE      CREATED    TAGS"
        if tab == "volumes":
            return "NAME                 DRIVER     MOUNTPOINT"
        if tab == "networks":
            return "NAME                 DRIVER     SUBNET"
        if tab == "compose":
            return "NAME                 STATUS     CONFIG FILES"
        return ""

    def _render_list(self) -> str:
        if self.selected_tab == "stats":
            stats = StatsCollector().collect_stats(
                self.containers,
                self.images,
                self.volumes,
                self.networks,
                self.composes,
                self.self_usage,
            )
            c = stats["containers"]
            i = stats["images"]
            v = stats["volumes"]
            n = stats["networks"]
            cp = stats["compose"]
            return "\n".join(
                [
                    "DOCKER STATISTICS",
                    "",
                    f"Containers: total={c['total']} running={c['running']} stopped={c['stopped']} paused={c['paused']}",
                    f"Container avg cpu={c.get('avg_cpu', 0.0):.1f}% avg mem={c.get('avg_memory', 0.0):.1f}MB",
                    f"Images: total={i['total']} size={i.get('total_size_gb', 0.0):.2f}GB",
                    f"Volumes: total={v['total']}",
                    f"Networks: total={n['total']}",
                    f"Compose projects: total={cp['total']}",
                    f"App usage: {self.self_usage}",
                ]
            )

        items = self._get_tab_items()
        list_height = max(8, self.query_one("#list", Static).size.height - 3)
        if self.selected_index < self.scroll_offset:
            self.scroll_offset = self.selected_index
        elif self.selected_index >= self.scroll_offset + list_height:
            self.scroll_offset = self.selected_index - list_height + 1

        visible = items[self.scroll_offset : self.scroll_offset + list_height]

        lines = [self._header(self.selected_tab), ""]
        selected_ids = self.bulk_selected.get(self.selected_tab, set())
        for i, item in enumerate(visible):
            actual_idx = self.scroll_offset + i
            marker = ">" if actual_idx == self.selected_index else " "

            if self.bulk_select_mode and self.selected_tab in self.bulk_selected:
                item_id = self._item_id(self.selected_tab, item)
                checkbox = "[x]" if item_id in selected_ids else "[ ]"
                prefix = f"{marker} {checkbox}"
            else:
                prefix = f"{marker}  "

            lines.append(f"{prefix} {self._row(self.selected_tab, item)}")

        if not visible:
            lines.append("(no items)")

        return "\n".join(lines)

    def _render_details(self) -> str:
        if self.selected_tab == "stats":
            return "Use tabs 1-6 and Enter for actions."

        selected = self._selected_item()
        if not selected:
            return "No selection"

        if self.selected_tab == "containers":
            details = [
                f"ID: {selected.id}",
                f"Name: {selected.name}",
                f"Status: {selected.status}",
                f"Image: {selected.image}",
                "",
                "Logs:",
                "-" * 40,
            ]
            details.extend(self.logs[-60:])
            return "\n".join(details)

        if self.selected_tab == "images":
            return "\n".join(
                [
                    f"ID: {selected.id}",
                    f"Tags: {selected.tags}",
                    f"Size: {selected.size_mb:.1f}MB",
                    f"Created: {selected.created}",
                ]
            )

        if self.selected_tab == "volumes":
            return "\n".join(
                [
                    f"Name: {selected.name}",
                    f"Driver: {selected.driver}",
                    f"Mountpoint: {selected.mountpoint}",
                ]
            )

        if self.selected_tab == "networks":
            return "\n".join(
                [
                    f"ID: {selected.id}",
                    f"Name: {selected.name}",
                    f"Driver: {selected.driver}",
                    f"Subnet: {selected.subnet}",
                ]
            )

        return "\n".join(
            [
                f"Project: {selected.name}",
                f"Status: {selected.status}",
                f"Config: {selected.config_files}",
            ]
        )

    def _render_status(self) -> str:
        filter_part = f"FILTER: {self.filter_text}" if self.is_filtering else ""
        bulk_part = "BULK ON" if self.bulk_select_mode else "BULK OFF"
        return f"{bulk_part}  {filter_part}  {self.message}".strip()

    def _render(self) -> None:
        self.query_one("#tabs", Static).update(rich_escape(self._format_tabs()))
        self.query_one("#list", Static).update(rich_escape(self._render_list()))
        self.query_one("#details", Static).update(rich_escape(self._render_details()))
        self.query_one("#status", Static).update(rich_escape(self._render_status()))

    def _tick(self) -> None:
        self._refresh_all()
        self._render()

    async def _confirm(self, question: str) -> bool:
        result = await self.push_screen_wait(ConfirmScreen(question))
        return bool(result)

    async def _input(self, prompt: str) -> Optional[str]:
        result = await self.push_screen_wait(InputScreen(prompt))
        return result

    async def _choose_action(self, options: list[tuple[str, str]]) -> Optional[str]:
        return await self.push_screen_wait(ActionMenuScreen("Actions", options))

    def _run_external(self, cmd: Any, shell: bool = False) -> None:
        try:
            with self.suspend():
                subprocess.call(cmd, shell=shell)
        except Exception as exc:
            self._set_message(f"Error: {exc}")

    async def _dispatch_bulk_action(self, key: str) -> bool:
        selected_ids = sorted(self.bulk_selected.get(self.selected_tab, set()))
        if not selected_ids:
            self._set_message("No items selected")
            return False

        if self.selected_tab == "containers":
            if key == "s":
                for cid in selected_ids:
                    self.backend.start_container(cid)
                self._set_message(f"Started {len(selected_ids)} containers")
                return True
            if key == "t" and await self._confirm(f"Stop {len(selected_ids)} containers?"):
                for cid in selected_ids:
                    self.backend.stop_container(cid)
                self._set_message(f"Stopped {len(selected_ids)} containers")
                return True
            if key == "r":
                for cid in selected_ids:
                    self.backend.restart_container(cid)
                self._set_message(f"Restarted {len(selected_ids)} containers")
                return True
            if key == "d" and await self._confirm(f"Remove {len(selected_ids)} containers?"):
                for cid in selected_ids:
                    self.backend.remove_container(cid)
                self._set_message(f"Removed {len(selected_ids)} containers")
                return True

        if self.selected_tab == "images":
            if key == "d" and await self._confirm(f"Remove {len(selected_ids)} images?"):
                for iid in selected_ids:
                    self.backend.remove_image(iid)
                self._set_message(f"Removed {len(selected_ids)} images")
                return True
            if key == "p" and await self._confirm("Prune unused Docker resources?"):
                self.backend.prune_all()
                self._set_message("Pruned unused resources")
                return True

        if self.selected_tab == "volumes" and key == "d" and await self._confirm(f"Remove {len(selected_ids)} volumes?"):
            for vid in selected_ids:
                self.backend.remove_volume(vid)
            self._set_message(f"Removed {len(selected_ids)} volumes")
            return True

        if self.selected_tab == "networks" and key == "d" and await self._confirm(f"Remove {len(selected_ids)} networks?"):
            for nid in selected_ids:
                self.backend.remove_network(nid)
            self._set_message(f"Removed {len(selected_ids)} networks")
            return True

        if self.selected_tab == "compose":
            if key == "U":
                for name in selected_ids:
                    comp = next((c for c in self.composes if c.name == name), None)
                    self.backend.compose_up(name, comp.config_files if comp else "")
                self._set_message(f"Started {len(selected_ids)} compose projects")
                return True
            if key == "D" and await self._confirm(f"Stop {len(selected_ids)} compose projects?"):
                for name in selected_ids:
                    comp = next((c for c in self.composes if c.name == name), None)
                    self.backend.compose_down(name, comp.config_files if comp else "")
                self._set_message(f"Stopped {len(selected_ids)} compose projects")
                return True
            if key == "r" and await self._confirm(f"Remove {len(selected_ids)} compose projects?"):
                for name in selected_ids:
                    comp = next((c for c in self.composes if c.name == name), None)
                    self.backend.compose_remove(name, comp.config_files if comp else "")
                self._set_message(f"Removed {len(selected_ids)} compose projects")
                return True

        return False

    async def _dispatch_single_action(self, key: str) -> bool:
        item = self._selected_item()
        if not item and self.selected_tab != "images":
            return False

        tab = self.selected_tab

        if tab == "containers" and item:
            if key == "s":
                self.backend.start_container(item.id)
                return True
            if key == "t" and await self._confirm("Stop container?"):
                self.backend.stop_container(item.id)
                return True
            if key == "r":
                self.backend.restart_container(item.id)
                return True
            if key == "z":
                if item.status == "paused":
                    self.backend.unpause_container(item.id)
                elif item.status == "running":
                    self.backend.pause_container(item.id)
                return True
            if key == "n":
                new_name = await self._input("New Name")
                if new_name:
                    self.backend.rename_container(item.id, new_name)
                    return True
            if key == "k":
                repo = await self._input("Repository")
                tag = await self._input("Tag (optional)")
                if repo:
                    self.backend.commit_container(item.id, repo, tag if tag else None)
                    return True
            if key == "cp":
                src = await self._input("Source Path")
                dest = await self._input("Destination Path in container")
                if src and dest:
                    self.backend.copy_to_container(item.id, src, dest)
                    return True
            if key == "x":
                self._run_external(["docker", "exec", "-it", item.id, "/bin/bash"])
                return True
            if key == "l":
                self._run_external(f"docker logs {item.id} 2>&1 | less -R", shell=True)
                return True

        if tab == "images":
            if key == "B":
                path = await self._input("Build path (default .)")
                path = path or "."
                tag = await self._input("Tag (e.g. myimage:latest)")
                if tag:
                    self._run_external(["docker", "build", "-t", tag, path])
                    return True
            if key == "L":
                path = await self._input("Load image file (.tar)")
                if path:
                    self.backend.load_image(path)
                    return True

            if item:
                if key == "p":
                    tag = item.tags[0] if item.tags else ""
                    if tag and tag != "<none>":
                        self._run_external(["docker", "pull", tag])
                        return True
                if key == "R":
                    name = await self._input("Container name (optional)")
                    self.backend.run_container(item.id, name if name else None)
                    return True
                if key == "S":
                    path = await self._input("Save image file (.tar)")
                    if path:
                        self.backend.save_image(item.id, path)
                        return True
                if key == "H":
                    self._run_external(f"docker history {item.id} | less", shell=True)
                    return True

        if tab == "volumes":
            if key == "C":
                name = await self._input("Volume name")
                if name:
                    self.backend.create_volume(name)
                    return True

        if tab == "compose" and item:
            if key == "U":
                self.backend.compose_up(item.name, item.config_files)
                return True
            if key == "D":
                self.backend.compose_down(item.name, item.config_files)
                return True
            if key in ("r", "R"):
                self.backend.compose_remove(item.name, item.config_files)
                return True
            if key == "P":
                self.backend.compose_pause(item.name, item.config_files)
                return True

        if key == "i" and item:
            cmd_type = "container"
            if tab == "images":
                cmd_type = "image"
            elif tab == "volumes":
                cmd_type = "volume"
            elif tab == "networks":
                cmd_type = "network"
            item_id = self._item_id(tab, item)
            self._run_external(f"docker inspect {cmd_type} {item_id} | less", shell=True)
            return True

        if key == "d" and item and await self._confirm(f"Delete {tab[:-1]}?"):
            if tab == "containers":
                self.backend.remove_container(item.id)
            elif tab == "images":
                self.backend.remove_image(item.id)
            elif tab == "volumes":
                self.backend.remove_volume(item.name)
            elif tab == "networks":
                self.backend.remove_network(item.id)
            return True

        if key == "P" and await self._confirm("Prune system (all unused)?"):
            self.backend.prune_all()
            return True

        return False

    async def _dispatch_user_action(self, key: str) -> None:
        handled = False
        if self.bulk_select_mode:
            handled = await self._dispatch_bulk_action(key)
        else:
            handled = await self._dispatch_single_action(key)

        if handled:
            self._refresh_all(force=True)

    async def action_open_menu(self) -> None:
        if self.selected_tab == "stats":
            return

        if self.bulk_select_mode:
            options_map = {
                "containers": [("Start All", "s"), ("Stop All", "t"), ("Restart All", "r"), ("Remove All", "d")],
                "images": [("Remove All", "d"), ("Prune Unused", "p")],
                "volumes": [("Remove All", "d")],
                "networks": [("Remove All", "d")],
                "compose": [("Up All", "U"), ("Down All", "D"), ("Remove All", "r")],
            }
        else:
            options_map = {
                "containers": [("Start", "s"), ("Stop", "t"), ("Restart", "r"), ("Pause/Unpause", "z"), ("Rename", "n"), ("Commit", "k"), ("Copy To", "cp"), ("Exec Shell", "x"), ("Logs", "l"), ("Inspect", "i"), ("Delete", "d")],
                "images": [("Run", "R"), ("Pull/Update", "p"), ("Save (tar)", "S"), ("Load (tar)", "L"), ("History", "H"), ("Build", "B"), ("Inspect", "i"), ("Delete", "d")],
                "volumes": [("Create", "C"), ("Inspect", "i"), ("Delete", "d")],
                "networks": [("Inspect", "i"), ("Delete", "d")],
                "compose": [("Up", "U"), ("Down", "D"), ("Remove", "r"), ("Pause", "P")],
            }

        options = options_map.get(self.selected_tab, [])
        if not options:
            return

        action_key = await self._choose_action(options)
        if action_key:
            await self._dispatch_user_action(action_key)
            self._render()

    def action_tab_containers(self) -> None:
        self._set_tab("containers")

    def action_tab_images(self) -> None:
        self._set_tab("images")

    def action_tab_volumes(self) -> None:
        self._set_tab("volumes")

    def action_tab_networks(self) -> None:
        self._set_tab("networks")

    def action_tab_compose(self) -> None:
        self._set_tab("compose")

    def action_tab_stats(self) -> None:
        self._set_tab("stats")

    def _set_tab(self, tab: str) -> None:
        self.selected_tab = tab
        self.selected_index = 0
        self.scroll_offset = 0
        self.filter_text = ""
        self.is_filtering = False
        self.bulk_select_mode = False
        self._refresh_all(force=True)
        self._render()

    def action_up(self) -> None:
        items = self._get_tab_items()
        if items:
            self.selected_index = max(0, self.selected_index - 1)
        self._render()

    def action_down(self) -> None:
        items = self._get_tab_items()
        if items:
            self.selected_index = min(len(items) - 1, self.selected_index + 1)
        self._render()

    def action_page_up(self) -> None:
        self.selected_index = max(0, self.selected_index - 10)
        self._render()

    def action_page_down(self) -> None:
        items = self._get_tab_items()
        if items:
            self.selected_index = min(len(items) - 1, self.selected_index + 10)
        self._render()

    def action_start_filter(self) -> None:
        self.is_filtering = True
        self.filter_text = ""
        self._set_message("Filtering mode")
        self._render()

    def action_clear_filter(self) -> None:
        self.filter_text = ""
        self.is_filtering = False
        self.selected_index = 0
        self._render()

    def action_toggle_bulk(self) -> None:
        if self.selected_tab == "stats":
            return
        self.bulk_select_mode = not self.bulk_select_mode
        self._set_message("Bulk mode ON" if self.bulk_select_mode else "Bulk mode OFF")
        self._render()

    def action_toggle_select(self) -> None:
        if not self.bulk_select_mode:
            return
        item = self._selected_item()
        if not item:
            return
        item_id = self._item_id(self.selected_tab, item)
        selected = self.bulk_selected.setdefault(self.selected_tab, set())
        if item_id in selected:
            selected.remove(item_id)
        else:
            selected.add(item_id)
        self._render()

    def action_select_all(self) -> None:
        if not self.bulk_select_mode:
            return
        items = self._get_tab_items()
        selected = self.bulk_selected.setdefault(self.selected_tab, set())
        selected.clear()
        for item in items:
            selected.add(self._item_id(self.selected_tab, item))
        self._render()

    def action_select_none(self) -> None:
        if not self.bulk_select_mode:
            return
        self.bulk_selected.setdefault(self.selected_tab, set()).clear()
        self._render()

    def action_cycle_sort(self) -> None:
        if self.selected_tab != "containers":
            return
        modes = ["name", "status", "cpu"]
        idx = modes.index(self.sort_mode) if self.sort_mode in modes else 0
        self.sort_mode = modes[(idx + 1) % len(modes)]
        self._render()

    async def on_key(self, event: events.Key) -> None:
        # Prefer configured keybindings for quit/help/filter/toggle actions.
        if config_manager.is_key_binding(event.key, "quit"):
            self.exit()
            return

        if self.is_filtering:
            if event.key == "escape":
                self.is_filtering = False
            elif event.key == "enter":
                self.is_filtering = False
            elif event.key == "backspace":
                self.filter_text = self.filter_text[:-1]
            elif event.character and event.character.isprintable():
                self.filter_text += event.character
            self.selected_index = 0
            self._render()
            event.stop()
            return

        # Handle symbolic keybinding names from config (e.g. "space").
        if config_manager.is_key_binding(event.key, "select_toggle"):
            self.action_toggle_select()
            event.stop()
            return
        if config_manager.is_key_binding(event.key, "select_all"):
            self.action_select_all()
            event.stop()
            return
        if config_manager.is_key_binding(event.key, "select_none"):
            self.action_select_none()
            event.stop()
            return

        if event.character:
            if event.character in ["B", "L"] and self.selected_tab == "images":
                await self._dispatch_user_action(event.character)
                self._render()
                event.stop()
                return

            direct_keys = {
                "s", "t", "r", "z", "n", "k", "x", "l", "i", "d", "p", "R", "S", "H", "C", "U", "D", "P"
            }
            if event.character in direct_keys:
                await self._dispatch_user_action(event.character)
                self._render()
                event.stop()


def run() -> None:
    app = TockerTextualApp()
    app.run()
