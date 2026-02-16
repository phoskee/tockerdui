"""Textual-based UI for tockerdui."""

from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import time
from typing import Any, Optional

from textual import events
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Footer, Header, Input, Static, Tab, Tabs
from rich.markup import escape as rich_escape

from .backend import DockerBackend
from .cache import cache_manager
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
    BINDINGS = [
        Binding("up", "move_up", "Up", show=False),
        Binding("down", "move_down", "Down", show=False),
        Binding("enter", "select", "Select", show=False),
        Binding("escape", "cancel", "Cancel", show=False),
    ]

    def __init__(self, title: str, options: list[tuple[str, str]]) -> None:
        super().__init__()
        self.menu_title = title
        self.options = options
        self.index = 0

    def compose(self) -> ComposeResult:
        yield Vertical(
            Static(self.menu_title, classes="modal_title"),
            Static("", id="menu_options", classes="modal_body"),
            Static("[Up/Down] Move  [Enter] Select  [Esc] Cancel", classes="modal_hint"),
            id="modal",
        )

    def on_mount(self) -> None:
        self._render_options()

    def _render_options(self) -> None:
        lines = []
        for idx, (label, key) in enumerate(self.options):
            marker = ">" if idx == self.index else " "
            lines.append(f"{marker} {label} ({key})")
        self.query_one("#menu_options", Static).update("\n".join(lines))

    def action_move_up(self) -> None:
        self.index = (self.index - 1) % len(self.options)
        self._render_options()

    def action_move_down(self) -> None:
        self.index = (self.index + 1) % len(self.options)
        self._render_options()

    def action_select(self) -> None:
        self.dismiss(self.options[self.index][1])

    def action_cancel(self) -> None:
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
      layout: vertical;
      height: 1fr;
    }

    #top {
      height: 1fr;
    }

    #list {
      width: 58%;
      height: 1fr;
      border: round $accent;
      padding: 0 1;
      overflow: auto;
    }

    #info {
      width: 42%;
      height: 1fr;
      border: round $accent;
      padding: 0 1;
      overflow: auto;
    }

    #logs {
      height: 2fr;
      border: round $accent;
      padding: 0 1;
      overflow: auto;
    }

    Screen.narrow #list {
      width: 100%;
      height: 1fr;
    }

    Screen.narrow #info {
      display: none;
    }

    Screen.compact #logs {
      display: none;
    }

    Screen.compact #top {
      height: 1fr;
    }

    Screen.no-logs #logs {
      display: none;
    }

    Screen.no-logs #top {
      height: 1fr;
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
        Binding("1", "tab_containers", "Containers", show=False),
        Binding("2", "tab_images", "Images", show=False),
        Binding("3", "tab_volumes", "Volumes", show=False),
        Binding("4", "tab_networks", "Networks", show=False),
        Binding("5", "tab_compose", "Compose", show=False),
        Binding("6", "tab_stats", "Stats", show=False),
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
        Binding("y", "copy_text", "Copy"),
        Binding("e", "export_view", "Export"),
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
        self._last_container_stats = 0.0
        self._force_refresh = True
        self._refresh_in_flight = False
        self._syncing_tabs = False

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Tabs(
            Tab("CONTAINERS", id="containers"),
            Tab("IMAGES", id="images"),
            Tab("VOLUMES", id="volumes"),
            Tab("NETWORKS", id="networks"),
            Tab("COMPOSE", id="compose"),
            Tab("STATS", id="stats"),
            id="tabs",
        )
        yield Vertical(
            Horizontal(
                Static("", id="list", markup=False),
                Static("", id="info", markup=False),
                id="top",
            ),
            Static("", id="logs", markup=False),
            id="main",
        )
        yield Static("", id="status", markup=False)
        yield Footer()

    def on_mount(self) -> None:
        self.set_interval(0.25, self._tick)
        self._apply_responsive_layout()
        self.query_one("#tabs", Tabs).active = self.selected_tab
        self._apply_panel_mode()
        self._render()

    def on_resize(self, event: events.Resize) -> None:
        self._apply_responsive_layout()
        self._apply_panel_mode()
        self._normalize_selection()
        self._render()

    def _apply_responsive_layout(self) -> None:
        # Small terminals: hide logs and stack panes to preserve selection visibility.
        self.set_class(self.size.width < 120, "narrow")
        self.set_class(self.size.height < 26, "compact")

    def _apply_panel_mode(self) -> None:
        # Logs are meaningful only for containers; hide panel in other tabs.
        self.set_class(self.selected_tab != "containers", "no-logs")

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

    async def _refresh_all(self, force: bool = False) -> None:
        now = time.monotonic()

        if force or now - self._last_containers >= 1.0:
            containers_task = asyncio.to_thread(self.backend.get_containers)
            usage_task = asyncio.to_thread(self.backend.get_self_usage)
            new_containers, self.self_usage = await asyncio.gather(
                containers_task, usage_task
            )
            # Preserve displayed CPU/MEM between container list refreshes to avoid visual reset/flicker.
            previous_stats = {
                c.id: (getattr(c, "cpu_percent", "--"), getattr(c, "ram_usage", "--"))
                for c in self.containers
            }
            for c in new_containers:
                if c.id in previous_stats:
                    c.cpu_percent, c.ram_usage = previous_stats[c.id]
                elif c.status != "running":
                    c.cpu_percent, c.ram_usage = "0.0%", "0.0MB"
            self.containers = new_containers
            self._last_containers = now

        if force or now - self._last_container_stats >= 2.0:
            running = [c for c in self.containers if c.status == "running"]
            if running:
                stats = await asyncio.gather(
                    *[
                        asyncio.to_thread(self.backend.get_container_stats, c.id)
                        for c in running
                    ]
                )
                for c, (cpu, ram) in zip(running, stats):
                    c.cpu_percent = cpu
                    c.ram_usage = ram
            for c in self.containers:
                if c.status != "running":
                    c.cpu_percent = "0.0%"
                    c.ram_usage = "0.0MB"
            self._last_container_stats = now

        if force or now - self._last_others >= 5.0:
            (
                self.images,
                self.volumes,
                self.networks,
                self.composes,
            ) = await asyncio.gather(
                asyncio.to_thread(self.backend.get_images),
                asyncio.to_thread(self.backend.get_volumes),
                asyncio.to_thread(self.backend.get_networks),
                asyncio.to_thread(self.backend.get_composes),
            )
            self._last_others = now

        self._normalize_selection()

        if self.selected_tab == "containers":
            selected = self._selected_item()
            if selected:
                self.logs = await asyncio.to_thread(
                    self.backend.get_logs, selected.id, 100
                )

    def _set_message(self, message: str) -> None:
        self.message = message

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
        list_height = max(1, self.query_one("#list", Static).size.height - 3)
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

    def _render_info(self) -> str:
        if self.selected_tab == "stats":
            return "Use tabs and Enter for actions."

        selected = self._selected_item()
        if not selected:
            return "No selection"

        if self.selected_tab == "containers":
            details = [
                f"ID: {selected.id}",
                f"Name: {selected.name}",
                f"Status: {selected.status}",
                f"Image: {selected.image}",
            ]
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

    def _render_logs(self) -> str:
        if self.selected_tab != "containers":
            return "Logs are available in CONTAINERS tab."
        if not self.logs:
            return "(no logs)"
        return "\n".join(self.logs[-200:])

    def _render_status(self) -> str:
        filter_part = f"FILTER: {self.filter_text}" if self.is_filtering else ""
        bulk_part = "BULK ON" if self.bulk_select_mode else "BULK OFF"
        return f"{bulk_part}  {filter_part}  {self.message}".strip()

    def _render(self) -> None:
        self.query_one("#list", Static).update(rich_escape(self._render_list()))
        self.query_one("#info", Static).update(rich_escape(self._render_info()))
        self.query_one("#logs", Static).update(rich_escape(self._render_logs()))
        self.query_one("#status", Static).update(rich_escape(self._render_status()))

    async def _tick(self) -> None:
        if self._refresh_in_flight:
            return
        self._refresh_in_flight = True
        try:
            force = self._force_refresh
            self._force_refresh = False
            await self._refresh_all(force=force)
            self._render()
        finally:
            self._refresh_in_flight = False

    async def _confirm(self, question: str) -> bool:
        result = await self.push_screen_wait(ConfirmScreen(question))
        return bool(result)

    async def _input(self, prompt: str) -> Optional[str]:
        result = await self.push_screen_wait(InputScreen(prompt))
        return result

    async def _choose_action(self, options: list[tuple[str, str]]) -> Optional[str]:
        return await self.push_screen_wait(ActionMenuScreen("Actions", options))

    async def _run_backend(self, func: Any, *args: Any) -> Any:
        return await asyncio.to_thread(func, *args)

    def _run_external(self, cmd: list[str], pager: bool = False) -> None:
        try:
            with self.suspend():
                if pager and shutil.which("less"):
                    proc = subprocess.Popen(
                        cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                    )
                    if proc.stdout is None:
                        subprocess.call(cmd)
                    else:
                        less_proc = subprocess.Popen(["less", "-R"], stdin=proc.stdout)
                        proc.stdout.close()
                        less_proc.wait()
                        return_code = proc.wait()
                        if return_code != 0:
                            self._set_message(
                                f"Command failed (exit {return_code}): {' '.join(cmd[:3])}"
                            )
                else:
                    return_code = subprocess.call(cmd)
                    if return_code != 0:
                        self._set_message(
                            f"Command failed (exit {return_code}): {' '.join(cmd[:3])}"
                        )
        except Exception as exc:
            self._set_message(f"Error: {exc}")

    def _run_compose_external(self, project_name: str, config_files: str, args: list[str], pager: bool = False) -> None:
        cmd = ["docker", "compose", "-p", project_name]
        if config_files and config_files != "n/a":
            for file_path in [p.strip() for p in config_files.split(",") if p.strip()]:
                cmd.extend(["-f", file_path])
        cmd.extend(args)
        self._run_external(cmd, pager=pager)

    def _current_text_for_copy(self) -> str:
        if self.selected_tab == "containers":
            return self._render_logs() or self._render_info()
        return self._render_info()

    def _copy_to_clipboard(self, text: str) -> bool:
        if not text.strip():
            self._set_message("Nothing to copy")
            return False
        try:
            if shutil.which("pbcopy"):
                subprocess.run(["pbcopy"], input=text, text=True, check=False)
                return True
            if shutil.which("xclip"):
                subprocess.run(
                    ["xclip", "-selection", "clipboard"],
                    input=text,
                    text=True,
                    check=False,
                )
                return True
            if shutil.which("wl-copy"):
                subprocess.run(["wl-copy"], input=text, text=True, check=False)
                return True
        except Exception:
            return False
        return False

    def _compose_result_message(
        self, action: str, project_name: str, result: tuple[bool, str]
    ) -> str:
        ok, msg = result
        if msg:
            return msg
        if ok:
            return f"Compose {action} succeeded for '{project_name}'"
        return f"Compose {action} failed for '{project_name}'"

    async def _dispatch_bulk_action(self, key: str) -> bool:
        selected_ids = sorted(self.bulk_selected.get(self.selected_tab, set()))
        if not selected_ids:
            self._set_message("No items selected")
            return False

        if self.selected_tab == "containers":
            if key == "s":
                for cid in selected_ids:
                    await self._run_backend(self.backend.start_container, cid)
                self._set_message(f"Started {len(selected_ids)} containers")
                return True
            if key == "t" and await self._confirm(f"Stop {len(selected_ids)} containers?"):
                for cid in selected_ids:
                    await self._run_backend(self.backend.stop_container, cid)
                self._set_message(f"Stopped {len(selected_ids)} containers")
                return True
            if key == "r":
                for cid in selected_ids:
                    await self._run_backend(self.backend.restart_container, cid)
                self._set_message(f"Restarted {len(selected_ids)} containers")
                return True
            if key == "d" and await self._confirm(f"Remove {len(selected_ids)} containers?"):
                for cid in selected_ids:
                    await self._run_backend(self.backend.remove_container, cid)
                self._set_message(f"Removed {len(selected_ids)} containers")
                return True

        if self.selected_tab == "images":
            if key == "d" and await self._confirm(f"Remove {len(selected_ids)} images?"):
                failures = 0
                for iid in selected_ids:
                    if not await self._run_backend(self.backend.remove_image, iid):
                        failures += 1
                msg = f"Removed {len(selected_ids) - failures}/{len(selected_ids)} images"
                if failures:
                    msg += f" ({failures} failed)"
                self._set_message(msg)
                return True
            if key == "p" and await self._confirm("Prune unused Docker resources?"):
                await self._run_backend(self.backend.prune_all)
                self._set_message("Pruned unused resources")
                return True

        if self.selected_tab == "volumes" and key == "d" and await self._confirm(f"Remove {len(selected_ids)} volumes?"):
            for vid in selected_ids:
                await self._run_backend(self.backend.remove_volume, vid)
            self._set_message(f"Removed {len(selected_ids)} volumes")
            return True

        if self.selected_tab == "networks" and key == "d" and await self._confirm(f"Remove {len(selected_ids)} networks?"):
            for nid in selected_ids:
                await self._run_backend(self.backend.remove_network, nid)
            self._set_message(f"Removed {len(selected_ids)} networks")
            return True

        if self.selected_tab == "compose":
            failures = 0
            if key == "U":
                for name in selected_ids:
                    comp = next((c for c in self.composes if c.name == name), None)
                    ok, _ = await self._run_backend(
                        self.backend.compose_up, name, comp.config_files if comp else ""
                    )
                    if not ok:
                        failures += 1
                msg = f"Started {len(selected_ids)} compose projects"
                if failures:
                    msg += f" ({failures} failed)"
                self._set_message(msg)
                return True
            if key == "D" and await self._confirm(f"Stop {len(selected_ids)} compose projects?"):
                for name in selected_ids:
                    comp = next((c for c in self.composes if c.name == name), None)
                    ok, _ = await self._run_backend(
                        self.backend.compose_down,
                        name, comp.config_files if comp else ""
                    )
                    if not ok:
                        failures += 1
                msg = f"Stopped {len(selected_ids)} compose projects"
                if failures:
                    msg += f" ({failures} failed)"
                self._set_message(msg)
                return True
            if key == "X":
                for name in selected_ids:
                    comp = next((c for c in self.composes if c.name == name), None)
                    ok, _ = await self._run_backend(
                        self.backend.compose_restart,
                        name, comp.config_files if comp else ""
                    )
                    if not ok:
                        failures += 1
                msg = f"Restarted {len(selected_ids)} compose projects"
                if failures:
                    msg += f" ({failures} failed)"
                self._set_message(msg)
                return True
            if key == "p":
                for name in selected_ids:
                    comp = next((c for c in self.composes if c.name == name), None)
                    ok, _ = await self._run_backend(
                        self.backend.compose_pull,
                        name, comp.config_files if comp else ""
                    )
                    if not ok:
                        failures += 1
                msg = f"Pulled {len(selected_ids)} compose projects"
                if failures:
                    msg += f" ({failures} failed)"
                self._set_message(msg)
                return True
            if key == "r" and await self._confirm(f"Remove {len(selected_ids)} compose projects?"):
                for name in selected_ids:
                    comp = next((c for c in self.composes if c.name == name), None)
                    ok, _ = await self._run_backend(
                        self.backend.compose_remove,
                        name, comp.config_files if comp else ""
                    )
                    if not ok:
                        failures += 1
                msg = f"Removed {len(selected_ids)} compose projects"
                if failures:
                    msg += f" ({failures} failed)"
                self._set_message(msg)
                return True

        return False

    async def _dispatch_single_action(self, key: str) -> bool:
        item = self._selected_item()
        if not item and self.selected_tab != "images":
            return False

        tab = self.selected_tab

        if tab == "containers" and item:
            if key == "s":
                await self._run_backend(self.backend.start_container, item.id)
                return True
            if key == "t" and await self._confirm("Stop container?"):
                await self._run_backend(self.backend.stop_container, item.id)
                return True
            if key == "r":
                await self._run_backend(self.backend.restart_container, item.id)
                return True
            if key == "z":
                if item.status == "paused":
                    await self._run_backend(self.backend.unpause_container, item.id)
                elif item.status == "running":
                    await self._run_backend(self.backend.pause_container, item.id)
                return True
            if key == "n":
                new_name = await self._input("New Name")
                if new_name:
                    await self._run_backend(self.backend.rename_container, item.id, new_name)
                    return True
            if key == "k":
                repo = await self._input("Repository")
                tag = await self._input("Tag (optional)")
                if repo:
                    await self._run_backend(
                        self.backend.commit_container, item.id, repo, tag if tag else None
                    )
                    return True
            if key == "cp":
                src = await self._input("Source Path")
                dest = await self._input("Destination Path in container")
                if src and dest:
                    await self._run_backend(self.backend.copy_to_container, item.id, src, dest)
                    return True
            if key == "x":
                self._run_external(["docker", "exec", "-it", item.id, "/bin/bash"])
                return True
            if key == "l":
                self._run_external(["docker", "logs", item.id], pager=True)
                return True

        if tab == "images":
            if key == "B":
                path = await self._input("Build path (default .)")
                path = path or "."
                tag = await self._input("Tag (e.g. myimage:latest)")
                if tag:
                    self._run_external(["docker", "build", "-t", tag, path])
                    cache_manager.invalidate("images")
                    return True
            if key == "L":
                path = await self._input("Load image file (.tar)")
                if path:
                    await self._run_backend(self.backend.load_image, path)
                    return True

            if item:
                if key == "p":
                    tag = item.tags[0] if item.tags else ""
                    if tag and tag != "<none>":
                        self._run_external(["docker", "pull", tag])
                        cache_manager.invalidate("images")
                        return True
                if key == "R":
                    name = await self._input("Container name (optional)")
                    await self._run_backend(
                        self.backend.run_container, item.id, name if name else None
                    )
                    return True
                if key == "S":
                    path = await self._input("Save image file (.tar)")
                    if path:
                        await self._run_backend(self.backend.save_image, item.id, path)
                        return True
                if key == "H":
                    self._run_external(["docker", "history", item.id], pager=True)
                    return True

        if tab == "volumes":
            if key == "C":
                name = await self._input("Volume name")
                if name:
                    await self._run_backend(self.backend.create_volume, name)
                    return True

        if tab == "compose" and item:
            if key == "U":
                result = await self._run_backend(
                    self.backend.compose_up, item.name, item.config_files
                )
                self._set_message(self._compose_result_message("up", item.name, result))
                return True
            if key == "D":
                result = await self._run_backend(
                    self.backend.compose_down, item.name, item.config_files
                )
                self._set_message(self._compose_result_message("down", item.name, result))
                return True
            if key in ("r", "R"):
                result = await self._run_backend(
                    self.backend.compose_remove, item.name, item.config_files
                )
                self._set_message(
                    self._compose_result_message("remove", item.name, result)
                )
                return True
            if key == "P":
                result = await self._run_backend(
                    self.backend.compose_pause, item.name, item.config_files
                )
                self._set_message(
                    self._compose_result_message("pause", item.name, result)
                )
                return True
            if key == "X":
                result = await self._run_backend(
                    self.backend.compose_restart, item.name, item.config_files
                )
                self._set_message(
                    self._compose_result_message("restart", item.name, result)
                )
                return True
            if key == "p":
                result = await self._run_backend(
                    self.backend.compose_pull, item.name, item.config_files
                )
                self._set_message(
                    self._compose_result_message("pull", item.name, result)
                )
                return True
            if key == "l":
                self._run_compose_external(
                    item.name,
                    item.config_files,
                    ["logs", "--tail", "200"],
                    pager=True,
                )
                return True

        if key == "i" and item:
            item_id = self._item_id(tab, item)
            inspect_cmd = ["docker", "container", "inspect", item_id]
            if tab == "images":
                inspect_cmd = ["docker", "image", "inspect", item_id]
            elif tab == "volumes":
                inspect_cmd = ["docker", "volume", "inspect", item_id]
            elif tab == "networks":
                inspect_cmd = ["docker", "network", "inspect", item_id]
            self._run_external(inspect_cmd, pager=True)
            return True

        if key == "d" and item and await self._confirm(f"Delete {tab[:-1]}?"):
            if tab == "containers":
                await self._run_backend(self.backend.remove_container, item.id)
            elif tab == "images":
                removed = await self._run_backend(self.backend.remove_image, item.id)
                if not removed:
                    self._set_message("Failed to remove image")
                    return False
            elif tab == "volumes":
                await self._run_backend(self.backend.remove_volume, item.name)
            elif tab == "networks":
                await self._run_backend(self.backend.remove_network, item.id)
            return True

        if key == "P" and await self._confirm("Prune system (all unused)?"):
            await self._run_backend(self.backend.prune_all)
            return True

        return False

    async def _dispatch_user_action(self, key: str) -> None:
        handled = False
        if self.bulk_select_mode:
            handled = await self._dispatch_bulk_action(key)
        else:
            handled = await self._dispatch_single_action(key)

        if handled:
            self._force_refresh = True

    def action_open_menu(self) -> None:
        self.run_worker(
            self._open_menu_flow(),
            group="user-action",
            exclusive=True,
            thread=False,
        )

    async def _open_menu_flow(self) -> None:
        if self.selected_tab == "stats":
            return

        if self.bulk_select_mode:
            options_map = {
                "containers": [("Start All", "s"), ("Stop All", "t"), ("Restart All", "r"), ("Remove All", "d")],
                "images": [("Remove All", "d"), ("Prune Unused", "p")],
                "volumes": [("Remove All", "d")],
                "networks": [("Remove All", "d")],
                "compose": [("Up All", "U"), ("Down All", "D"), ("Restart All", "X"), ("Pull All", "p"), ("Remove All", "r")],
            }
        else:
            options_map = {
                "containers": [("Start", "s"), ("Stop", "t"), ("Restart", "r"), ("Pause/Unpause", "z"), ("Rename", "n"), ("Commit", "k"), ("Copy To", "cp"), ("Exec Shell", "x"), ("Logs", "l"), ("Inspect", "i"), ("Delete", "d")],
                "images": [("Run", "R"), ("Pull/Update", "p"), ("Save (tar)", "S"), ("Load (tar)", "L"), ("History", "H"), ("Build", "B"), ("Inspect", "i"), ("Delete", "d")],
                "volumes": [("Create", "C"), ("Inspect", "i"), ("Delete", "d")],
                "networks": [("Inspect", "i"), ("Delete", "d")],
                "compose": [("Up", "U"), ("Down", "D"), ("Restart", "X"), ("Pull", "p"), ("Logs", "l"), ("Remove", "r"), ("Pause", "P")],
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
        tabs = self.query_one("#tabs", Tabs)
        if tabs.active != tab:
            self._syncing_tabs = True
            try:
                tabs.active = tab
            finally:
                self._syncing_tabs = False
        self._apply_panel_mode()
        self._force_refresh = True
        self._render()

    def on_tabs_tab_activated(self, event: Tabs.TabActivated) -> None:
        if self._syncing_tabs:
            return
        tab_id = event.tab.id
        if tab_id in self.TABS and tab_id != self.selected_tab:
            self._set_tab(tab_id)

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

    def action_copy_text(self) -> None:
        text = self._current_text_for_copy()
        if self._copy_to_clipboard(text):
            self._set_message("Copied to clipboard")
            self._render()
        else:
            self._set_message("Clipboard not available (install xclip/wl-clipboard on Linux)")
            self._render()

    def action_export_view(self) -> None:
        self.run_worker(
            self._export_view_flow(),
            group="user-action",
            exclusive=True,
            thread=False,
        )

    async def _export_view_flow(self) -> None:
        default_path = os.path.expanduser(f"~/tockerdui-{self.selected_tab}.txt")
        path = await self._input(f"Export path (default: {default_path})")
        target = path or default_path
        content = "\n\n".join(
            [
                self._render_list(),
                "DETAILS",
                self._render_info(),
                "LOGS",
                self._render_logs(),
            ]
        )
        try:
            with open(target, "w", encoding="utf-8") as f:
                f.write(content)
            self._set_message(f"Exported to {target}")
        except Exception as exc:
            self._set_message(f"Export failed: {exc}")
        self._render()

    async def on_key(self, event: events.Key) -> None:
        # Prefer configured keybindings for quit/help/filter/toggle actions.
        if not self.is_filtering and config_manager.is_key_binding(event.key, "quit"):
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
                self.run_worker(
                    self._run_user_action_flow(event.character),
                    group="user-action",
                    exclusive=True,
                    thread=False,
                )
                event.stop()
                return

            direct_keys = {
                "s", "t", "r", "z", "n", "k", "x", "l", "i", "d", "p", "R", "S", "H", "C", "U", "D", "P", "X"
            }
            if event.character in direct_keys:
                self.run_worker(
                    self._run_user_action_flow(event.character),
                    group="user-action",
                    exclusive=True,
                    thread=False,
                )
                event.stop()

    async def _run_user_action_flow(self, key: str) -> None:
        await self._dispatch_user_action(key)
        self._render()

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool:
        # If a modal screen is active, app-level bindings must not steal keys.
        if len(self.screen_stack) > 1:
            return False
        # While filtering, disable all action bindings and let on_key manage text input.
        if self.is_filtering:
            return False
        return True


def run() -> None:
    app = TockerTextualApp()
    app.run()
