"""
Curses-based Terminal UI rendering engine.

This module handles all terminal rendering via the curses library. It provides:
  - Color initialization and color pair management
  - Multi-tab interface rendering
  - Resource list rendering (containers, images, volumes, networks)
  - Detail inspector panel (logs, stats, info)
  - Action menu dialogs
  - Help and confirmation modals

Rendering Strategy:
  - Single curses window (stdscr) with regions:
    - Header: Title + tab bar
    - Main: List view or inspector
    - Footer: Status, shortcuts
  - Differential rendering: only redraw if state changed (via version tracking)
  - Automatic layout calculation based on terminal size

Color Pairs (initialized in init_colors):
  1: White (default text)
  2: Green (running/success/selected)
  3: Red (error/stopped)
  4: Cyan (headers/borders)

Key Functions:
  - init_colors(): Initialize color pairs
  - draw_ui(): Main rendering dispatcher
  - draw_header(): Title and tab bar
  - draw_list(): Resource list with columns (container status, image size, etc.)
  - draw_inspector(): Detail view for selected item (logs, stats)
  - draw_*_modal(): Action menus (start/stop/delete/confirm)
  - draw_footer(): Status and keyboard shortcuts

Dependencies:
  - curses (Python built-in, terminal mode)
  - model.py for AppState dataclass

Limitations:
  - curses not available on Windows (use WSL)
  - Terminal must be >= 10 lines high (enforced with size checks)
  - No mouse support (keyboard-only)
"""

import curses
from dataclasses import dataclass
from typing import List, Callable
from .model import AppState
from .stats import StatsCollector, ChartRenderer

# --- COLUMN LAYOUT CONSTANTS ---

@dataclass
class ColumnLayout:
    """Defines column layout for a tab view."""
    columns: List[dict]  # List of {name, width, formatter}
    min_width: int = 40  # Minimum terminal width for this layout
    
    def render_header(self, term_width: int) -> str:
        """Render header row with column names."""
        header_parts = []
        for col in self.columns:
            if col.get('is_dynamic'):
                width = col['width']
            else:
                width = col['width']
            header_parts.append(f"{col['name']:<{width}}")
        return "  " + " ".join(header_parts)
    
    def render_row(self, item, tab: str) -> str:
        """Render a data row using formatters."""
        row_parts = []
        for col in self.columns:
            formatter = col.get('formatter')
            if formatter:
                value = formatter(item, tab)
            else:
                value = str(getattr(item, col['field'], ''))
            width = col['width']
            row_parts.append(f"{str(value):<{width}}")
        return "  " + " ".join(row_parts)

# Column width constants
COL_PROJECT = 12
COL_NAME_CONTAINER = 20
COL_STATUS = 10
COL_CPU = 7
COL_MEMORY = 10
COL_IMAGE = 20

COL_IMAGE_ID = 15
COL_SIZE = 10
COL_CREATED = 15

COL_DRIVER = 10
COL_NAME_RESOURCE = 20

COL_CONFIG_FILES = 25

def init_colors():
    curses.start_color()
    curses.use_default_colors()
    # High-quality color pairs
    curses.init_pair(1, curses.COLOR_WHITE, -1)    # Default
    curses.init_pair(2, curses.COLOR_GREEN, -1)    # Success / Running
    curses.init_pair(3, curses.COLOR_RED, -1)      # Error / Stopped
    curses.init_pair(4, curses.COLOR_CYAN, -1)     # Highlight / Secondary
    curses.init_pair(5, curses.COLOR_MAGENTA, -1)  # Project / Accent
    curses.init_pair(6, curses.COLOR_YELLOW, -1)   # Warning / Paused
    curses.init_pair(7, curses.COLOR_BLACK, curses.COLOR_CYAN) # Inverse Highlight

def draw_header(stdscr, width, current_tab):
    tabs = [
        ("CONTAINERS", "containers"),
        ("IMAGES", "images"),
        ("VOLUMES", "volumes"),
        ("NETWORKS", "networks"),
        ("COMPOSE", "compose"),
        ("STATS", "stats")
    ]
    
    # Title bar
    title = " tockerdui     "
    stdscr.attron(curses.color_pair(7) | curses.A_BOLD)
    stdscr.addstr(0, 0, title.center(width))
    stdscr.attroff(curses.color_pair(7) | curses.A_BOLD)
    
    # Tab bar
    x = 2
    for label, key in tabs:
        if key == current_tab:
            style = curses.color_pair(4) | curses.A_BOLD | curses.A_UNDERLINE
        else:
            style = curses.A_DIM
        stdscr.addstr(1, x, label, style)
        x += len(label) + 4
    
    stdscr.noutrefresh()

def draw_footer(stdscr, width, height, state: AppState):
    bar_y = height - 1
    stdscr.move(bar_y, 0)
    stdscr.clrtoeol()
    
    # Message / Error
    if state.message:
         stdscr.addstr(bar_y, 0, f" {state.message} ", curses.color_pair(3) | curses.A_BOLD)
    elif state.is_filtering:
        label = " FILTERING: "
        stdscr.addstr(bar_y, 0, label, curses.color_pair(7) | curses.A_BOLD)
        stdscr.addstr(bar_y, len(label), f" {state.filter_text} ", curses.A_BOLD)
    else:
        # Sort Indicator
        sort_info = f" [SORT: {state.sort_mode.upper()}] " if state.selected_tab == "containers" else ""
        # Shortcut bar
        focus_txt = f" TAB: Focus ({state.focused_pane.upper()}) "
        if state.bulk_select_mode:
            help_txt = "| SPACE: Toggle | A: All | D: None | B: Bulk OFF | Enter: Bulk Actions | q: Quit "
        else:
            help_txt = "| Enter: Menu | P: Prune | B: Bulk ON | q: Quit | ?: Help "
        
        # Draw Focus info
        try:
            if width > len(sort_info):
                stdscr.addstr(bar_y, 0, sort_info, curses.color_pair(5))
            x_pos = len(sort_info)
            
            if width > x_pos + len(focus_txt):
                stdscr.addstr(bar_y, x_pos, focus_txt, curses.color_pair(4) | curses.A_BOLD)
            x_pos += len(focus_txt)

            # Truncate help text if needed
            remaining_w = width - x_pos - 1
            if remaining_w > 5:
                # Reserve space for usage if possible
                usage_w = 20 # approx
                avail_w = remaining_w
                if state.self_usage: avail_w -= usage_w
                
                if avail_w > 5:
                    stdscr.addstr(bar_y, x_pos, help_txt[:avail_w], curses.A_DIM)
        except: pass
        
        # Draw Self Usage (Right aligned)
        try:
            if state.self_usage:
                usage_txt = f" [{state.self_usage}] "
                u_x = width - len(usage_txt) - 1
                if u_x > x_pos + 5: # Ensure at least some gap
                    stdscr.addstr(bar_y, u_x, usage_txt, curses.color_pair(6) | curses.A_BOLD)
        except: pass
    
    stdscr.noutrefresh()

def draw_list(win, state: AppState):
    """Render the resource list with dynamic column layout."""
    h, w = win.getmaxyx()
    win.erase()
    win.box()
    
    tab = state.selected_tab
    
    try:
        # Get items and title based on tab
        if tab == "containers":
            title, items = " Containers ", state.containers
        elif tab == "images":
            title, items = " Images ", state.images
        elif tab == "volumes":
            title, items = " Volumes ", state.volumes
        elif tab == "networks":
            title, items = " Networks ", state.networks
        elif tab == "compose":
            title, items = " Compose Projects ", state.composes
        elif tab == "stats":
            draw_stats_dashboard(win, state)
            return

        # Add filter and bulk mode indicators to title
        if state.filter_text:
            title += f" (Matches: '{state.filter_text}') "
        if state.bulk_select_mode:
            title += "[BULK] "

        # Render header
        win.addstr(0, 2, title, curses.A_BOLD | curses.color_pair(4))
        
        # Calculate dynamic widths based on terminal width
        header_txt = _get_header_for_tab(tab, w)
        win.addstr(1, 1, header_txt[:w-2], curses.color_pair(5) | curses.A_BOLD)

        # Render items with batch optimization
        start_y = 2
        max_items = h - 3
        offset = state.scroll_offset
        visible_items = items[offset : offset + max_items]
        
        # Pre-calculate styles to avoid repeated attribute access
        if tab == "containers":
            for i, item in enumerate(visible_items):
                actual_index = offset + i
                is_selected = (actual_index == state.selected_index)
                row_style = curses.color_pair(7) if is_selected else curses.A_NORMAL
                
                line = _format_row_for_tab(tab, item, w, is_selected)
                
                # Optimized status handling
                if item.status == "running": 
                    s_color = curses.color_pair(2)
                elif item.status == "paused": 
                    s_color = curses.color_pair(6)
                else: 
                    s_color = curses.color_pair(3)
                
                # Show checkbox in bulk mode or status indicator
                if state.bulk_select_mode:
                    checkbox = "[x]" if item.selected else "[ ]"
                    status_style = s_color | (curses.A_REVERSE if is_selected else 0)
                    win.addstr(start_y + i, 1, f" {checkbox} ", status_style)
                    win.addstr(start_y + i, 7, line[:w-8], row_style)
                else:
                    status_char = "*"
                    status_style = s_color | (curses.A_REVERSE if is_selected else 0)
                    win.addstr(start_y + i, 1, f" {status_char} ", status_style)
                    win.addstr(start_y + i, 5, line[:w-6], row_style)
        else:
            # Batch rendering for non-container tabs
            for i, item in enumerate(visible_items):
                actual_index = offset + i
                is_selected = (actual_index == state.selected_index)
                row_style = curses.color_pair(7) if is_selected else curses.A_NORMAL
                
                # Show checkbox in bulk mode
                if state.bulk_select_mode:
                    checkbox = "[x]" if item.selected else "[ ]"
                    win.addstr(start_y + i, 1, f" {checkbox} ", row_style)
                    line = _format_row_for_tab(tab, item, w, is_selected)
                    win.addstr(start_y + i, 6, line[:w-7].ljust(w-7), row_style)
                else:
                    line = _format_row_for_tab(tab, item, w, is_selected)
                    win.addstr(start_y + i, 1, line[:w-2].ljust(w-2), row_style)
    except Exception as e:
        pass  # Gracefully handle rendering errors
    
    win.noutrefresh()


def _get_header_for_tab(tab: str, term_width: int) -> str:
    """Generate header string for the given tab."""
    if tab == "containers":
        # Dynamic widths for containers
        fixed_width = COL_PROJECT + COL_STATUS + COL_CPU + COL_MEMORY + 6
        rem_width = max(10, term_width - fixed_width - 10)
        w_name = max(15, int(rem_width * 0.35))
        w_image = max(10, rem_width - w_name - 1)
        
        return (f"  {'PROJECT':<{COL_PROJECT}} {'NAME':<{w_name}} {'STATUS':<{COL_STATUS}} "
                f"{'CPU':<{COL_CPU}} {'MEM':<{COL_MEMORY}} {'IMAGE':<{w_image}}")
    
    elif tab == "images":
        fixed = COL_IMAGE_ID + COL_SIZE + COL_CREATED + 5
        w_tags = max(10, term_width - fixed)
        return f"  {'SHORT ID':<{COL_IMAGE_ID}} {'SIZE (MB)':<{COL_SIZE}} {'CREATED':<{COL_CREATED}} {'TAGS':<{w_tags}}"
    
    elif tab == "volumes":
        rem_w = max(20, term_width - COL_DRIVER - 5)
        w_name = max(15, int(rem_w * 0.4))
        return f"  {'NAME':<{w_name}} {'DRIVER':<{COL_DRIVER}} {'MOUNT'}"
    
    elif tab == "networks":
        rem_w = max(20, term_width - COL_DRIVER - 5)
        w_name = max(15, int(rem_w * 0.4))
        return f"  {'NAME':<{w_name}} {'DRIVER':<{COL_DRIVER}} {'SUBNET'}"
    
    else:  # compose
        rem_w = max(20, term_width - COL_STATUS - 5)
        w_name = max(15, int(rem_w * 0.4))
        return f"  {'NAME':<{w_name}} {'STATUS':<{COL_STATUS}} {'CONFIG FILES'}"


def _format_row_for_tab(tab: str, item, term_width: int, is_selected: bool) -> str:
    """Format a single row for the given tab."""
    if tab == "containers":
        # Dynamic widths (must match header)
        fixed_width = COL_PROJECT + COL_STATUS + COL_CPU + COL_MEMORY + 6
        rem_width = max(10, term_width - fixed_width - 10)
        w_name = max(15, int(rem_width * 0.35))
        w_image = max(10, rem_width - w_name - 1)
        
        name_str = item.name[:w_name-1]
        image_str = item.image[:w_image-1]
        
        return (f"  {item.project[:COL_PROJECT-1]:<{COL_PROJECT}} {name_str:<{w_name}} "
                f"{item.status[:COL_STATUS-1]:<{COL_STATUS}} {item.cpu_percent:<{COL_CPU}} "
                f"{item.ram_usage:<{COL_MEMORY}} {image_str:<{w_image}}")
    
    elif tab == "images":
        fixed = COL_IMAGE_ID + COL_SIZE + COL_CREATED + 5
        w_tags = max(10, term_width - fixed)
        return (f"  {item.short_id:<{COL_IMAGE_ID}} {item.size_mb:<{COL_SIZE}.1f} "
                f"{item.created:<{COL_CREATED}} {str(item.tags)[:w_tags]}")
    
    elif tab == "volumes":
        rem_w = max(20, term_width - COL_DRIVER - 5)
        w_name = max(15, int(rem_w * 0.4))
        return f"  {item.name[:w_name-1]:<{w_name}} {item.driver:<{COL_DRIVER}} {item.mountpoint}"
    
    elif tab == "networks":
        rem_w = max(20, term_width - COL_DRIVER - 5)
        w_name = max(15, int(rem_w * 0.4))
        return f"  {item.name[:w_name-1]:<{w_name}} {item.driver:<{COL_DRIVER}} {item.subnet}"
    
    else:  # compose
        rem_w = max(20, term_width - COL_STATUS - 5)
        w_name = max(15, int(rem_w * 0.4))
        return f"  {item.name[:w_name-1]:<{w_name}} {item.status:<{COL_STATUS}} {item.config_files}"


def draw_details(win, state: AppState):
    h, w = win.getmaxyx()
    win.erase()
    
    # Highlight if focused
    is_focused = (state.focused_pane == "details")
    border_color = curses.color_pair(4) if is_focused else curses.color_pair(1)
    
    win.attron(border_color)
    win.box()
    title = " INSPECTOR / LOGS "
    win.addstr(0, 2, title, curses.A_BOLD if is_focused else curses.A_NORMAL)
    win.attroff(border_color)
    
    header_lines = []
    idx = state.selected_index
    tab = state.selected_tab
    
    if tab == "containers" and idx < len(state.containers):
        c = state.containers[idx]
        header_lines.append(f"  ID:      {c.id[:12]}...")
        header_lines.append(f"  Name:    {c.name}")
        header_lines.append(f"  Status:  {c.status.upper()} (CPU: {c.cpu_percent}, RAM: {c.ram_usage})")
        header_lines.append(f"  Image:   {c.image}")
        header_lines.append(" " + "-" * (w - 4))
        # Logs handled separately
            
    elif tab == "images" and idx < len(state.images):
        img = state.images[idx]
        header_lines.append(f"  ID:   {img.id}")
        header_lines.append(f"  Tags: {img.tags}")
        
    elif tab == "volumes" and idx < len(state.volumes):
        v = state.volumes[idx]
        header_lines.append(f"  Name:  {v.name}")
        header_lines.append(f"  Mount: {v.mountpoint}")
        
    elif tab == "networks" and idx < len(state.networks):
        n = state.networks[idx]
        header_lines.append(f"  ID:     {n.id[:12]}...")
        header_lines.append(f"  Name:   {n.name}")
        header_lines.append(f"  Subnet: {n.subnet}")
    
    elif tab == "compose" and idx < len(state.composes):
        c = state.composes[idx]
        header_lines.append(f"  Project: {c.name}")
        header_lines.append(f"  Status:  {c.status}")
        header_lines.append(f"  Files:   {c.config_files}")

    # Draw Headers
    try:
        current_y = 1
        for line in header_lines:
            if current_y >= h - 1: break
            win.addstr(current_y, 1, line[:w-3])
            current_y += 1

        # Draw Logs (only for containers for now)
        if tab == "containers" and current_y < h - 1:
            available_lines = h - 1 - current_y
            offset = state.logs_scroll_offset
            
            # If auto-following (at bottom), should we check?
            # For now just respect offset.
            
            # Ensure offset is valid (state manager handles it, but just in case of race)
            if offset >= len(state.logs): offset = max(0, len(state.logs) - available_lines)
            
            visible_logs = state.logs[offset : offset + available_lines]
            
            for i, log in enumerate(visible_logs):
                if current_y + i >= h - 1: break
                try:
                    # Truncate or wrap? Truncate for now to avoid mess
                    win.addstr(current_y + i, 1, f"  {log}"[:w-3])
                except: pass
    except: pass
            
    win.noutrefresh()

def prompt_input(stdscr, cy, cx, prompt):
    max_h, max_w = stdscr.getmaxyx()
    box_w = min(60, max_w - 4)
    box_h = 3
    
    # Ensure starting position is valid
    start_y = max(0, min(cy - 1, max_h - box_h))
    start_x = max(0, min(cx - box_w//2, max_w - box_w))
    
    win = curses.newwin(box_h, box_w, start_y, start_x)
    win.keypad(True)
    win.attron(curses.color_pair(4))
    win.box()
    win.attroff(curses.color_pair(4))
    
    # Truncate prompt if too long
    avail_w = box_w - 4
    if len(prompt) > avail_w: prompt = prompt[:avail_w-3] + "..."
    win.addstr(1, 2, prompt, curses.A_BOLD)
    win.refresh()
    
    text = ""
    curses.noecho()
    curses.curs_set(1)
    
    while True:
        # Redraw
        win.erase()
        win.attron(curses.color_pair(4))
        win.box()
        win.attroff(curses.color_pair(4))
        win.addstr(1, 2, prompt + text)
        win.refresh()
        
        ch = win.getch()
        
        if ch == 27: # ESC
            curses.curs_set(0)
            return None
        elif ch in (10, 13): # Enter
            curses.curs_set(0)
            return text.strip()
        elif ch in (curses.KEY_BACKSPACE, 127):
            text = text[:-1]
        elif 32 <= ch <= 126:
            if len(prompt) + len(text) < box_w - 4:
                text += chr(ch)
    
    return None

def ask_confirmation(stdscr, cy, cx, question: str) -> bool:
    max_h, max_w = stdscr.getmaxyx()
    msg = f" {question} (Y/n) "
    
    width = min(max(30, len(msg) + 4), max_w - 2)
    height = 5
    
    start_y = max(0, min(cy - height//2, max_h - height))
    start_x = max(0, min(cx - width//2, max_w - width))
    
    win = curses.newwin(height, width, start_y, start_x)
    win.attron(curses.color_pair(3)) # Yellow/Red border
    win.box()
    win.attroff(curses.color_pair(3))
    
    # Center message safely
    trunc_msg = msg if len(msg) < width - 2 else msg[:width-5] + "..."
    win.addstr(1, max(1, (width - len(trunc_msg)) // 2), trunc_msg, curses.A_BOLD)
    
    selected = True # Yes by default
    
    while True:
        # Draw buttons
        y_btn = 3
        # Ensure buttons fit
        if width < 25: 
            x_yes = 1
            x_no = width // 2 + 1
            btn_yes = "[Y]"
            btn_no = "[N]"
        else:
            x_yes = width // 2 - 8
            x_no = width // 2 + 4
            btn_yes = " [ YES ] "
            btn_no = " [ NO ] "
        
        style_yes = curses.A_REVERSE if selected else curses.A_NORMAL
        style_no = curses.A_REVERSE if not selected else curses.A_NORMAL
        
        try:
            win.addstr(y_btn, x_yes, btn_yes, style_yes)
            win.addstr(y_btn, x_no, btn_no, style_no)
        except: pass
        
        win.refresh()
        
        key = win.getch()
        if key == curses.KEY_LEFT or key == curses.KEY_RIGHT or key == ord('\t'):
            selected = not selected
        elif key in (10, 13, ord('y'), ord('Y')):
            return True if selected else False
        elif key in (27, ord('n'), ord('N')):
            return False
        elif key == ord('q'): return False

def action_menu(stdscr, cy, cx, tab, item_id, bulk_mode=False):
    max_h, max_w = stdscr.getmaxyx()
    actions = []
    if tab == "containers":
        if bulk_mode:
            actions = [("Start All", "s"), ("Stop All", "t"), ("Restart All", "r"), ("Remove All", "d")]
        else:
            actions = [("Start", "s"), ("Stop", "t"), ("Restart", "r"), ("Pause/Unpause", "z"), ("Rename", "n"), ("Commit", "k"), ("Copy To", "cp"), ("Exec Shell", "x"), ("Logs", "l"), ("Inspect", "i"), ("Delete", "d")]
    elif tab == "images":
        if bulk_mode:
            actions = [("Remove All", "d"), ("Prune Unused", "p")]
        else:
            actions = [("Run", "R"), ("Pull/Update", "p"), ("Save (tar)", "S"), ("Load (tar)", "L"), ("History", "H"), ("Build", "B"), ("Inspect", "i"), ("Delete", "d")]
    elif tab == "volumes":
        if bulk_mode:
            actions = [("Remove All", "d")]
        else:
            actions = [("Create", "C"), ("Inspect", "i"), ("Delete", "d")]
    elif tab == "networks":
        if bulk_mode:
            actions = [("Remove All", "d")]
        else:
            actions = [("Inspect", "i"), ("Delete", "d")]
    elif tab == "compose":
        if bulk_mode:
            actions = [("Up All", "U"), ("Down All", "D"), ("Remove All", "r")]
        else:
            actions = [("Up", "U"), ("Down", "D"), ("Restart", "r"), ("Pull", "P")]

    if not actions: return None

    width = min(30, max_w - 4)
    height = min(len(actions) + 2, max_h - 4)
    
    start_y = max(0, min(cy - height//2, max_h - height))
    start_x = max(0, min(cx - width//2, max_w - width))
    
    win = curses.newwin(height, width, start_y, start_x)
    win.attron(curses.color_pair(4))
    win.box()
    win.attroff(curses.color_pair(4))
    win.keypad(True)
    
    selected = 0
    top_scroll = 0
    visible_rows = height - 2
    
    while True:
        for i in range(visible_rows):
            idx = top_scroll + i
            if idx >= len(actions): break
            
            label, _ = actions[idx]
            is_sel = (idx == selected)
            style = curses.color_pair(7) if is_sel else curses.A_NORMAL
            
            # Draw scroll indicators
            prefix = " "
            if i == 0 and top_scroll > 0: prefix = "^"
            elif i == visible_rows - 1 and top_scroll + visible_rows < len(actions): prefix = "v"
            
            try:
                display_label = label[:width-5]
                win.addstr(i + 1, 1, f"{prefix} {display_label:<{width-4}}", style)
            except: pass
            
        win.refresh()
        
        key = win.getch()
        if key == curses.KEY_UP: 
            selected = (selected - 1) % len(actions)
            if selected < top_scroll: top_scroll = selected
            elif selected >= top_scroll + visible_rows: top_scroll = selected - visible_rows + 1 # Wrap around logic handled by % but simple scrolling needed
            # Actually easier: just keep selected in view
            if selected < top_scroll: top_scroll = selected
            if selected >= len(actions) - 1: # Wrapped to bottom
                 top_scroll = max(0, len(actions) - visible_rows)
            
        elif key == curses.KEY_DOWN: 
            selected = (selected + 1) % len(actions)
            if selected >= top_scroll + visible_rows: top_scroll = selected - visible_rows + 1
            if selected == 0: top_scroll = 0 # Wrapped to top

        elif key in (10, 13): return actions[selected][1]
        elif key == 27: return None

def draw_help_modal(stdscr, cy, cx):
    max_h, max_w = stdscr.getmaxyx()
    lines = [
        " tockerdui HELP ",
        "------------------",
        " Navigation:",
        "  1-5         : Switch Tabs",
        "  Up/Down     : Select Item",
        "  Enter       : Actions Menu",
        "  /           : Search Filter",
        "  TAB         : Toggle Focus",
        "  q           : Quit",
        "",
        " Global Actions:",
        "  P           : Prune System (Confirm)",
        "  U           : Check Updates",
        "",
        " Container Actions:",
        "  s/t/r       : Start/Stop/Restart",
        "  z/x/l       : Pause/Shell/Logs",
        "  d           : Delete (Confirm)",
        "",
        " Image Actions:",
        "  R/p         : Run/Pull",
        "  B/H         : Build/History",
        "  d           : Delete (Confirm)",
        "",
        " Press any key to close "
    ]
    width = min(50, max_w - 2)
    height = min(len(lines) + 2, max_h - 2)
    
    start_y = max(0, min(cy - height//2, max_h - height))
    start_x = max(0, min(cx - width//2, max_w - width))
    
    win = curses.newwin(height, width, start_y, start_x)
    win.attron(curses.color_pair(4))
    win.box()
    win.attroff(curses.color_pair(4))
    
    visible_lines = height - 2
    for i in range(visible_lines):
        if i >= len(lines): break
        line = lines[i]
        try:
            if i == 0: 
                win.addstr(1+i, max(1, (width-len(line))//2), line[:width-2], curses.A_BOLD | curses.color_pair(4))
            else: 
                win.addstr(1+i, 2, line[:width-4])
        except: pass
        
    win.refresh()
    win.getch()

# ... (stats dashboard remains unchanged)

def draw_update_modal(stdscr, cy, cx):
    max_h, max_w = stdscr.getmaxyx()
    lines = [
        " UPDATE AVAILABLE ",
        "------------------",
        "",
        " A new version of tockerdui is available!",
        "",
        " Do you want to update now?",
        " (The app will restart)",
        "",
        " [Y]es   [N]o "
    ]
    width = min(46, max_w - 4)
    height = min(len(lines) + 2, max_h - 4)
    
    start_y = max(0, min(cy - height//2, max_h - height))
    start_x = max(0, min(cx - width//2, max_w - width))
    
    win = curses.newwin(height, width, start_y, start_x)
    win.attron(curses.color_pair(4))
    win.box()
    win.attroff(curses.color_pair(4))
    
    for i, line in enumerate(lines):
        if i >= height - 2: break
        try:
            if i == 0: 
                win.addstr(1+i, max(1, (width-len(line))//2), line[:width-2], curses.A_BOLD | curses.color_pair(2))
            else:
                win.addstr(1+i, 2, line[:width-4])
        except: pass
            
    win.refresh()

def draw_error_footer(stdscr: 'curses._CursesWindow', w: int, h: int, state: 'AppState') -> None:
    """
    Draw error message in footer with RED color if error is recent (< 3 seconds).
    
    Args:
        stdscr: Curses window
        w: Terminal width
        h: Terminal height
        state: Application state
    """
    import time
    
    if not state.last_error:
        return
    
    current_time = time.time()
    time_elapsed = current_time - state.error_timestamp
    
    # Auto-clear error after 3 seconds
    if time_elapsed > 3.0:
        return
    
    # Display error in bottom-left corner with RED color
    error_line = state.last_error[:w-2]  # Truncate to fit width
    try:
        stdscr.attron(curses.color_pair(3))  # RED color
        stdscr.addstr(h - 1, 1, f"ERROR: {error_line}", curses.A_BOLD | curses.color_pair(3))
        stdscr.attroff(curses.color_pair(3))
    except curses.error:
        # Ignore if window is too small or position invalid
        pass
