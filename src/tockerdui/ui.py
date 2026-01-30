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
from .model import AppState

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
        ("COMPOSE", "compose")
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
        help_txt = "| Enter: Menu | P: Prune | q: Quit | ?: Help "
        
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
    h, w = win.getmaxyx()
    win.erase()
    win.box()
    
    # Selection of items and headers
    tab = state.selected_tab
    
    # Dynamic Column Widths
    # Base padding: 2 (start) + 1 (gap) * N = ~6 chars reserved for structure
    # Define widths map: {tab: (header_str, item_formatter_func)}
    
    try:
        if tab == "containers":
            title, items = " Containers ", state.containers
            # Fixed cols: 
            # Project: 12, Status: 10, CPU: 7, Mem: 10 => Total Fixed ~40
            # Dynamic: Name, Image
            
            fixed_width = 12 + 10 + 7 + 10 + 6 # +6 for spaces/bullet
            rem_width = max(10, w - fixed_width)
            
            # Allocate 35% to Name, remainder to Image, but keep min 20 for name
            w_name = max(20, int(rem_width * 0.35))
            w_image = max(10, rem_width - w_name - 1)
            
            header = f"  {'PROJECT':<12} {'NAME':<{w_name}} {'STATUS':<10} {'CPU':<7} {'MEM':<10} {'IMAGE'}"
            
        elif tab == "images":
            title, items = " Images ", state.images
            w_id = 15
            w_size = 10
            w_created = 15
            fixed = w_id + w_size + w_created + 5
            w_tags = max(10, w - fixed)
            header = f"  {'SHORT ID':<{w_id}} {'SIZE (MB)':<{w_size}} {'CREATED':<{w_created}} {'TAGS'}"
            
        elif tab == "volumes":
            title, items = " Volumes ", state.volumes
            w_driver = 10
            rem_w = max(20, w - w_driver - 5)
            w_name = max(20, int(rem_w * 0.4))
            # w_mount = rem_w - w_name
            header = f"  {'NAME':<{w_name}} {'DRIVER':<{w_driver}} {'MOUNT'}"
            
        elif tab == "networks":
            title, items = " Networks ", state.networks
            w_driver = 10
            rem_w = max(20, w - w_driver - 5)
            w_name = max(20, int(rem_w * 0.4))
            header = f"  {'NAME':<{w_name}} {'DRIVER':<{w_driver}} {'SUBNET'}"
            
        else: # compose
            title, items = " Compose Projects ", state.composes
            w_status = 15
            rem_w = max(20, w - w_status - 5)
            w_name = max(20, int(rem_w * 0.4))
            header = f"  {'NAME':<{w_name}} {'STATUS':<{w_status}} {'CONFIG FILES'}"

        # Filtered title
        if state.filter_text:
            title += f" (Matches: '{state.filter_text}') "

        win.addstr(0, 2, title, curses.A_BOLD | curses.color_pair(4))
        win.addstr(1, 1, header[:w-2], curses.color_pair(5) | curses.A_BOLD)

        start_y = 2
        max_items = h - 3
        offset = state.scroll_offset
        visible_items = items[offset : offset + max_items]
        
        for i, item in enumerate(visible_items):
            actual_index = offset + i
            is_selected = (actual_index == state.selected_index)
            
            row_style = curses.color_pair(7) if is_selected else curses.A_NORMAL
            
            if tab == "containers":
                # Simple bullet
                status_char = "*" 
                if item.status == "running": s_color = curses.color_pair(2)
                elif item.status == "paused": s_color = curses.color_pair(6)
                else: s_color = curses.color_pair(3)
                
                win.addstr(start_y + i, 1, f" {status_char} ", s_color | (curses.A_REVERSE if is_selected else 0))
                
                # Use dynamic widths calculated above
                name_str = item.name[:w_name-1]
                img_str = item.image[:w_image-1] if 'w_image' in locals() else item.image
                
                row_txt = f"{item.project[:11]:<12} {name_str:<{w_name}} {item.status[:9]:<10} {item.cpu_percent:<7} {item.ram_usage:<10} {img_str}"
                win.addstr(start_y + i, 5, row_txt[:w-6], row_style)
            else:
                if tab == "images":
                    line = f"  {item.short_id:<15} {item.size_mb:<10.1f} {item.created:<15} {str(item.tags)[:w_tags]}"
                elif tab == "volumes":
                    line = f"  {item.name[:w_name-1]:<{w_name}} {item.driver:<10} {item.mountpoint}"
                elif tab == "networks":
                    line = f"  {item.name[:w_name-1]:<{w_name}} {item.driver:<10} {item.subnet}"
                else: # compose
                    line = f"  {item.name[:w_name-1]:<{w_name}} {item.status:<15} {item.config_files}"
                
                win.addstr(start_y + i, 1, line[:w-2].ljust(w-2), row_style)
    except: pass
    
    win.noutrefresh()


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
    box_w = 60
    box_h = 3
    win = curses.newwin(box_h, box_w, cy - 1, cx - box_w//2)
    win.keypad(True)
    win.attron(curses.color_pair(4))
    win.box()
    win.attroff(curses.color_pair(4))
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
    # Generic Y/N modal
    msg = f" {question} (Y/n) "
    width = max(30, len(msg) + 4)
    height = 5
    win = curses.newwin(height, width, cy - height//2, cx - width//2)
    win.attron(curses.color_pair(3)) # Yellow/Red border
    win.box()
    win.attroff(curses.color_pair(3))
    win.addstr(1, 1, msg.center(width-2), curses.A_BOLD)
    
    selected = True # Yes by default
    
    while True:
        # Draw buttons
        y_btn = 3
        # Ensure buttons fit
        if width < 20: 
            x_yes = 1
            x_no = 8
        else:
            x_yes = width // 2 - 8
            x_no = width // 2 + 4
        
        style_yes = curses.A_REVERSE if selected else curses.A_NORMAL
        style_no = curses.A_REVERSE if not selected else curses.A_NORMAL
        
        try:
            win.addstr(y_btn, x_yes, " [ YES ] ", style_yes)
            win.addstr(y_btn, x_no, " [ NO ] ", style_no)
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

def action_menu(stdscr, cy, cx, tab, item_id):
    actions = []
    if tab == "containers":
        actions = [("Start", "s"), ("Stop", "t"), ("Restart", "r"), ("Pause/Unpause", "z"), ("Rename", "n"), ("Commit", "k"), ("Copy To", "cp"), ("Exec Shell", "x"), ("Logs", "l"), ("Inspect", "i"), ("Delete", "d")]
    elif tab == "images":
        actions = [("Run", "R"), ("Pull/Update", "p"), ("Save (tar)", "S"), ("Load (tar)", "L"), ("History", "H"), ("Build", "B"), ("Inspect", "i"), ("Delete", "d")]
    elif tab == "volumes":
        actions = [("Create", "C"), ("Inspect", "i"), ("Delete", "d")]
    elif tab == "networks":
        actions = [("Inspect", "i"), ("Delete", "d")]
    elif tab == "compose":
        actions = [("Up", "U"), ("Down", "D"), ("Restart", "r"), ("Pull", "P")]

    if not actions: return None

    width = 30
    height = len(actions) + 2
    win = curses.newwin(height, width, cy - height//2, cx - width//2)
    win.attron(curses.color_pair(4))
    win.box()
    win.attroff(curses.color_pair(4))
    win.keypad(True)
    
    selected = 0
    while True:
        for i, (label, _) in enumerate(actions):
            style = curses.color_pair(7) if i == selected else curses.A_NORMAL
            win.addstr(i + 1, 2, label.ljust(width - 4), style)
        win.refresh()
        
        key = win.getch()
        if key == curses.KEY_UP: selected = (selected - 1) % len(actions)
        elif key == curses.KEY_DOWN: selected = (selected + 1) % len(actions)
        elif key in (10, 13): return actions[selected][1]
        elif key == 27: return None

def draw_help_modal(stdscr, cy, cx):
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
    width = 50
    height = len(lines) + 2
    win = curses.newwin(height, width, cy - height//2, cx - width//2)
    win.attron(curses.color_pair(4))
    win.box()
    win.attroff(curses.color_pair(4))
    for i, line in enumerate(lines):
        if i == 0: win.addstr(1+i, (width-len(line))//2, line, curses.A_BOLD | curses.color_pair(4))
        else: win.addstr(1+i, 2, line)
    win.refresh()
    win.getch()

def draw_update_modal(stdscr, cy, cx):
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
    width = 46
    height = len(lines) + 2
    win = curses.newwin(height, width, cy - height//2, cx - width//2)
    win.attron(curses.color_pair(4))
    win.box()
    win.attroff(curses.color_pair(4))
    
    for i, line in enumerate(lines):
        if i == 0: 
            win.addstr(1+i, (width-len(line))//2, line, curses.A_BOLD | curses.color_pair(2))
        elif "[Y]es" in line:
            # Highlight options
            start = (width - len(line)) // 2
            win.addstr(1+i, start, line)
            # win.addstr(1+i, start + line.find("[Y]"), "[Y]es", curses.color_pair(2) | curses.A_BOLD)
            # win.addstr(1+i, start + line.find("[N]"), "[N]o", curses.color_pair(3) | curses.A_BOLD)
        else:
            win.addstr(1+i, 2, line)
            
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
