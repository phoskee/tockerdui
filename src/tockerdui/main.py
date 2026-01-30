"""
Main UI event loop and orchestration for tockerdui.

This module contains the main application loop that coordinates between:
  - curses terminal UI (rendering via ui.py)
  - Docker backend API (docker_backend)
  - Application state management (state.py with threading workers)
  - User input handling (keyboard navigation and actions)

Architecture:
  1. Initialize curses and spawn background workers (ListWorker, StatsWorker, LogsWorker)
  2. Main loop:
     - Poll user input (non-blocking getch)
     - Handle keyboard navigation (tabs, selection, filtering)
     - Dispatch actions (start/stop/restart containers, etc.)
     - Re-render UI only on state changes (differential updates)
  3. Workers periodically update state (containers every 1s, others every 5s)
  4. UI reads state and renders to terminal (curses)

Key Functions:
  - main(): Entry point, initializes curses and starts loop
  - handle_action(): Dispatches keyboard commands to backend
  - draw_*(): Rendering functions (delegated to ui.py)

Thread Safety:
  - AppState uses locks for concurrent access from main thread + workers
  - No curses calls from worker threads (only in main thread)
"""

from typing import Optional, Any
import curses
import time
import subprocess
import os
import logging

# Setup logging
from . import get_log_path
logging.basicConfig(filename=get_log_path(), level=logging.DEBUG, 
                    format='%(asctime)s - %(levelname)s - %(message)s')


from .backend import DockerBackend
from .state import StateManager, ListWorker, LogsWorker, StatsWorker
from .ui import init_colors, draw_header, draw_list, draw_details, draw_footer, draw_error_footer, prompt_input, draw_help_modal, action_menu, draw_update_modal, ask_confirmation
from .main_bulk import handle_bulk_action
from .cache import cache_manager
from .config import config_manager

def handle_action(key: str, tab: str, item_id: Optional[str], backend: 'DockerBackend', 
                 stdscr: 'curses._CursesWindow', state_mgr: 'StateManager', 
                 state: 'AppState', list_worker: 'ListWorker') -> None:
    try:
        h, w = stdscr.getmaxyx()
        logging.debug(f"Handling action {key} for tab {tab}")
        action_taken = False
        
        # --- BULK ACTIONS ---
        if state.bulk_select_mode:
            selected_ids = state_mgr.get_selected_items()
            if not selected_ids:
                state_mgr.set_message("No items selected")
                return
                
            if key == 's' and tab == "containers":
                # Start all selected containers
                for container_id in selected_ids:
                    backend.start_container(container_id)
                state_mgr.set_message(f"Started {len(selected_ids)} containers")
                action_taken = True
                
            elif key == 't' and tab == "containers":
                # Stop all selected containers
                if ask_confirmation(stdscr, h//2, w//2, f"Stop {len(selected_ids)} containers?"):
                    for container_id in selected_ids:
                        backend.stop_container(container_id)
                    state_mgr.set_message(f"Stopped {len(selected_ids)} containers")
                    action_taken = True
                    
            elif key == 'r' and tab == "containers":
                # Restart all selected containers
                for container_id in selected_ids:
                    backend.restart_container(container_id)
                state_mgr.set_message(f"Restarted {len(selected_ids)} containers")
                action_taken = True
                
            elif key == 'd' and tab == "containers":
                # Remove all selected containers
                if ask_confirmation(stdscr, h//2, w//2, f"Remove {len(selected_ids)} containers?"):
                    for container_id in selected_ids:
                        backend.remove_container(container_id)
                    state_mgr.set_message(f"Removed {len(selected_ids)} containers")
                    action_taken = True
            
            elif key == 'd' and tab == "images":
                # Remove all selected images
                if ask_confirmation(stdscr, h//2, w//2, f"Remove {len(selected_ids)} images?"):
                    for image_id in selected_ids:
                        backend.remove_image(image_id)
                    state_mgr.set_message(f"Removed {len(selected_ids)} images")
                    action_taken = True
                    
            elif key == 'p' and tab == "images":
                # Prune unused Docker resources
                if ask_confirmation(stdscr, h//2, w//2, "Prune unused Docker resources?"):
                    curses.def_prog_mode()
                    curses.endwin()
                    try:
                        print("Pruning Docker resources...")
                        backend.prune_all()
                        print("Done. Press Enter to continue.")
                        input()
                    except Exception as e:
                        print(f"Error: {e}")
                        input()
                    curses.reset_prog_mode()
                    curses.curs_set(0)
                    stdscr.nodelay(True)
                    stdscr.clearok(True)
                    stdscr.refresh()
                    state_mgr.set_message("Pruned unused Docker resources")
                    action_taken = True
                
            elif key == 'd' and tab == "volumes":
                # Remove all selected volumes
                if ask_confirmation(stdscr, h//2, w//2, f"Remove {len(selected_ids)} volumes?"):
                    for volume_name in selected_ids:
                        backend.remove_volume(volume_name)
                    state_mgr.set_message(f"Removed {len(selected_ids)} volumes")
                    action_taken = True
                    
            elif key == 'd' and tab == "networks":
                # Remove all selected networks
                if ask_confirmation(stdscr, h//2, w//2, f"Remove {len(selected_ids)} networks?"):
                    for network_id in selected_ids:
                        backend.remove_network(network_id)
                    state_mgr.set_message(f"Removed {len(selected_ids)} networks")
                    action_taken = True
                    
            elif key == 'U' and tab == "compose":
                # Up all selected compose projects
                for project_name in selected_ids:
                    backend.compose_up(project_name)
                state_mgr.set_message(f"Started {len(selected_ids)} compose projects")
                action_taken = True
                
            elif key == 'D' and tab == "compose":
                # Down all selected compose projects
                if ask_confirmation(stdscr, h//2, w//2, f"Stop {len(selected_ids)} compose projects?"):
                    for project_name in selected_ids:
                        backend.compose_down(project_name)
                    state_mgr.set_message(f"Stopped {len(selected_ids)} compose projects")
                    action_taken = True
                    
            elif key == 'r' and tab == "compose":
                # Remove all selected compose projects
                if ask_confirmation(stdscr, h//2, w//2, f"Remove {len(selected_ids)} compose projects?"):
                    for project_name in selected_ids:
                        backend.compose_remove(project_name)
                    state_mgr.set_message(f"Removed {len(selected_ids)} compose projects")
                    action_taken = True
        
        # --- SINGLE ITEM ACTIONS ---
        else:
            # --- CONTAINER ACTIONS ---
            if key == 's' and tab == "containers":
                backend.start_container(item_id)
                action_taken = True
            elif key == 't' and tab == "containers":
                if ask_confirmation(stdscr, h//2, w//2, "Stop container?"):
                     backend.stop_container(item_id)
                     action_taken = True
            elif key == 'r' and tab == "containers":
                backend.restart_container(item_id)
                action_taken = True
            elif key == 'z' and tab == "containers":
                c_info = next((c for c in state.containers if c.id == item_id), None)
                if c_info:
                    if c_info.status == "paused": backend.unpause_container(item_id)
                    elif c_info.status == "running": backend.pause_container(item_id)
            elif key == 'n' and tab == "containers":
                new_name = prompt_input(stdscr, h//2, w//2, "New Name: ")
                if new_name: backend.rename_container(item_id, new_name)
            elif key == 'k' and tab == "containers":
                repo = prompt_input(stdscr, h//2, w//2, "Repository: ")
                tag = prompt_input(stdscr, h//2, w//2, "Tag (optional): ")
                if repo: backend.commit_container(item_id, repo, tag if tag else None)
            elif key == 'cp' and tab == "containers":
                src = prompt_input(stdscr, h//2, w//2, "Source Path: ")
                dest = prompt_input(stdscr, h//2, w//2, "Dest Path (in container): ")
                if src and dest: backend.copy_to_container(item_id, src, dest)
            elif key == 'x' and tab == "containers":
                curses.def_prog_mode()
                curses.endwin()
                try:
                    subprocess.call(["docker", "exec", "-it", item_id, "/bin/bash"])
                except Exception:
                    try: subprocess.call(["docker", "exec", "-it", item_id, "sh"])
                    except: pass
                curses.reset_prog_mode()
                curses.curs_set(0)
                stdscr.nodelay(True)
                stdscr.clearok(True)
                stdscr.refresh()
            elif key == 'l' and tab == "containers":
                curses.def_prog_mode()
                curses.endwin()
                try: subprocess.call(f"docker logs {item_id} 2>&1 | less -R", shell=True)
                except Exception: pass
                curses.reset_prog_mode()
                curses.curs_set(0)
                stdscr.nodelay(True)
                stdscr.clearok(True)
                stdscr.refresh()
        
        # --- COMMON ACTIONS ---
        if key == 'i':
            curses.def_prog_mode()
            curses.endwin()
            try:
                cmd_type = "container"
                if tab == "images": cmd_type = "image"
                elif tab == "volumes": cmd_type = "volume"
                elif tab == "networks": cmd_type = "network"
                subprocess.call(f"docker inspect {cmd_type} {item_id} | less", shell=True)
            except Exception: pass
            curses.reset_prog_mode()
            curses.curs_set(0)
            stdscr.nodelay(True)
            stdscr.clearok(True)
            stdscr.refresh()
            action_taken = True
        elif key == 'd' and not state.bulk_select_mode:
            if ask_confirmation(stdscr, h//2, w//2, f"Delete {tab[:-1]}?"):
                if tab == "containers": backend.remove_container(item_id)
                elif tab == "images": backend.remove_image(item_id)
                elif tab == "volumes": backend.remove_volume(item_id)
                elif tab == "networks": backend.remove_network(item_id)
                action_taken = True
        elif key == 'P':
             if ask_confirmation(stdscr, h//2, w//2, "Prune system (all unused)?"):
                  curses.def_prog_mode()
                  curses.endwin()
                  try: 
                      print("Pruning system...")
                      backend.prune_all()
                      print("Done.")
                      time.sleep(1)
                  except: pass
                  curses.reset_prog_mode()
                  curses.curs_set(0)
                  stdscr.nodelay(True)
                  stdscr.clearok(True)
                  stdscr.refresh()
                  action_taken = True
         
        # --- IMAGE ACTIONS ---
        if key == 'p' and tab == "images" and not state.bulk_select_mode:
            img_info = next((i for i in state.images if i.id == item_id), None)
            if img_info and img_info.tags:
                tag = img_info.tags[0]
                if tag != "<none>":
                    curses.def_prog_mode()
                    curses.endwin()
                    try:
                        subprocess.call(["docker", "pull", tag])
                        print("Press Enter to return...")
                        input()
                    except Exception: pass
                    curses.reset_prog_mode()
                    curses.curs_set(0)
                    stdscr.nodelay(True)
                    stdscr.clearok(True)
                    stdscr.refresh()
                    action_taken = True
        elif key == 'R' and tab == "images" and not state.bulk_select_mode:
            name = prompt_input(stdscr, h // 2, w // 2, "Container Name: ")
            backend.run_container(item_id, name if name else None)
            action_taken = True
        elif key == 'S' and tab == "images" and not state.bulk_select_mode:
            path = prompt_input(stdscr, h//2, w//2, "Save to (e.g. image.tar): ")
            if path: backend.save_image(item_id, path)
            action_taken = True
        elif key == 'L' and tab == "images" and not state.bulk_select_mode:
            path = prompt_input(stdscr, h//2, w//2, "Load from (e.g. image.tar): ")
            if path: backend.load_image(path)
            action_taken = True
        elif key == 'H' and tab == "images" and not state.bulk_select_mode:
            curses.def_prog_mode()
            curses.endwin()
            try:
                subprocess.call(f"docker history {item_id} | less", shell=True)
            except Exception: pass
            curses.reset_prog_mode()
            curses.curs_set(0)
            stdscr.nodelay(True)
            stdscr.clearok(True)
            stdscr.refresh()
        elif key == 'B' and tab == "images" and not state.bulk_select_mode:
            path = prompt_input(stdscr, h//2, w//2, "Path (default .): ")
            if not path: path = "."
            tag = prompt_input(stdscr, h//2, w//2, "Tag (e.g. myimage:latest): ")
            if tag:
                 curses.def_prog_mode()
                 curses.endwin()
                 try:
                     subprocess.call(["docker", "build", "-t", tag, path])
                     print("Press Enter to return...")
                     input()
                 except Exception: pass
                 curses.reset_prog_mode()
                 curses.curs_set(0)
                 stdscr.nodelay(True)
                 stdscr.clearok(True)
                 stdscr.refresh()
                 action_taken = True
        
        # --- VOLUME ACTIONS ---
        if key == 'C' and tab == "volumes" and not state.bulk_select_mode:
            name = prompt_input(stdscr, h // 2, w // 2, "Volume Name: ")
            if name: backend.create_volume(name)
            action_taken = True
         
        # --- COMPOSE ACTIONS ---
        if tab == "compose" and not state.bulk_select_mode and item_id:
            if key == 'U':
                backend.compose_up(item_id)
                state_mgr.set_message(f"Compose project '{item_id}' is starting...")
                action_taken = True
            elif key == 'D':
                backend.compose_down(item_id)
                state_mgr.set_message(f"Compose project '{item_id}' is stopping...")
                action_taken = True
            elif key == 'R':
                backend.compose_remove(item_id)
                state_mgr.set_message(f"Compose project '{item_id}' has been removed...")
                action_taken = True
            elif key == 'P':
                backend.compose_pause(item_id)
                state_mgr.set_message(f"Compose project '{item_id}' is pausing...")
                action_taken = True
        
        if action_taken:
            list_worker.force_refresh()
            
    except Exception as e:
        logging.error(f"Error in handle_action: {e}", exc_info=True)
        state_mgr.set_message(f"Error: {str(e)}")

def main(stdscr):
    logging.info("Main started")
    try:
        curses.curs_set(0)
        stdscr.nodelay(True)
        # Use configured refresh interval
        stdscr.timeout(config_manager.get_refresh_interval())
        init_colors()
        
        backend = DockerBackend()
        state_mgr = StateManager()
        
        list_worker = ListWorker(state_mgr, backend)
        logs_worker = LogsWorker(state_mgr, backend)
        stats_worker = StatsWorker(state_mgr, backend)
        
        list_worker.start()
        logs_worker.start()
        stats_worker.start()
        
        logging.info("Backend and Workers initialized")

        list_win = None
        detail_win = None
        last_version = -1
        last_h, last_w = -1, -1
        force_redraw = True

        while True:
            try:
                # Check for state changes (cheap)
                current_version = state_mgr.get_version()
                state_changed = (current_version != last_version)
                
                if state_changed or force_redraw:
                    state = state_mgr.get_snapshot() # Expensive-ish
                    h, w = stdscr.getmaxyx()
                    
                    if h != last_h or w != last_w:
                         logging.info(f"Resize: {h}x{w}")
                         stdscr.clear()
                         last_h, last_w = h, w
                         split_y = int(h * 0.6)
                         
                         if h < 10 or w < 20:
                             stdscr.addstr(0, 0, "Terminal too small!")
                             list_win = None
                             detail_win = None
                         else:
                             list_win_h = split_y - 2
                             if list_win_h > 0:
                                 list_win = curses.newwin(list_win_h, w, 2, 0)
                             
                             detail_win_h = h - split_y - 1
                             if detail_win_h > 0:
                                 detail_win = curses.newwin(detail_win_h, w, split_y, 0)
                     
                    # Draw components
                    draw_header(stdscr, w, state.selected_tab)
                    draw_footer(stdscr, w, h, state)
                    draw_error_footer(stdscr, w, h, state)
                    if list_win: draw_list(list_win, state)
                    if detail_win: draw_details(detail_win, state)
                    
                    curses.doupdate()
                    last_version = current_version
                    force_redraw = False 

                key = stdscr.getch()
                if key == curses.ERR: continue 

                if key == ord('q') and not state.is_filtering:
                    logging.info("Quitting")
                    list_worker.running = False
                    logs_worker.running = False
                    stats_worker.running = False
                    break
                
                if state.is_filtering:
                    if key == 27: state_mgr.set_filtering(False)
                    elif key in (10, 13): state_mgr.set_filtering(False)
                    elif key in (curses.KEY_BACKSPACE, 127):
                        state_mgr.set_filter_text(state.filter_text[:-1])
                    elif 32 <= key <= 126:
                        state_mgr.set_filter_text(state.filter_text + chr(key))
                    continue

                if state.update_available:
                     try:
                         # Acquire lock to prevent state changes during modal
                         state_mgr.acquire_lock()
                         try:
                             draw_update_modal(stdscr, h//2, w//2)
                             curses.doupdate()
                             # Blocking wait for Y/N (with lock held)
                             while True:
                                 key = stdscr.getch()
                                 if key in (ord('y'), ord('Y'), 10, 13):
                                     stdscr.clear()
                                     stdscr.addstr(h//2, w//2 - 10, "Updating... please wait.")
                                     stdscr.refresh()
                                     state_mgr.release_lock()  # Release before update
                                     backend.perform_update()
                                     return # Exit to restart
                                 elif key in (ord('n'), ord('N'), 27):
                                     state_mgr.set_update_available(False)
                                     stdscr.clear() # clear modal artifacts
                                     break
                         finally:
                             state_mgr.release_lock()
                     except NameError:
                         # Fallback if UI not updated
                         logging.error("draw_update_modal not defined")
                         state_mgr.set_update_available(False)
                     continue

                elif key == ord('1'): state_mgr.set_tab("containers")
                elif key == ord('2'): state_mgr.set_tab("images")
                elif key == ord('3'): state_mgr.set_tab("volumes")
                elif key == ord('4'): state_mgr.set_tab("networks")
                elif key == ord('5'): state_mgr.set_tab("compose")
                elif key == ord('6'): state_mgr.set_tab("stats")
                elif key == ord('\t') or key == 9:
                    state_mgr.toggle_focus()
                
                elif key == ord('b') or key == ord('B'):
                    # Toggle bulk select mode
                    state_mgr.toggle_bulk_select_mode()
                
                elif key == ord(' '):
                    # Space to toggle selection in bulk mode
                    if state.is_filtering:
                        state_mgr.set_filter_text(state.filter_text + ' ')
                    else:
                        state_mgr.toggle_item_selection()
                
                elif key == ord('a') or key == ord('A'):
                    # Select all in bulk mode
                    if state.bulk_select_mode:
                        state_mgr.select_all_items()
                
                elif key == ord('d') or key == ord('D'):
                    # Deselect all in bulk mode (only in bulk mode, not for delete action)
                    if state.bulk_select_mode:
                        state_mgr.deselect_all_items()
                
                elif key == curses.KEY_UP:
                    split_y = int(h * 0.6)
                    if state.focused_pane == "list":
                        page_height = max(1, (split_y - 2))
                        state_mgr.move_selection(-1, page_height)
                    else:
                        detail_h = h - split_y - 1
                        logs_h = max(1, detail_h - 5) # approx header
                        state_mgr.scroll_logs(-1, logs_h)
                
                elif key == curses.KEY_DOWN:
                    split_y = int(h * 0.6)
                    if state.focused_pane == "list":
                        page_height = max(1, (split_y - 2))
                        state_mgr.move_selection(1, page_height)
                    else:
                        detail_h = h - split_y - 1
                        logs_h = max(1, detail_h - 5)
                        state_mgr.scroll_logs(1, logs_h)
                
                elif key == curses.KEY_PPAGE: # Page Up
                    split_y = int(h * 0.6)
                    if state.focused_pane == "list":
                        page_height = max(1, (split_y - 2))
                        state_mgr.move_selection(-page_height, page_height)
                    else:
                        detail_h = h - split_y - 1
                        logs_h = max(1, detail_h - 5)
                        state_mgr.scroll_logs(-logs_h, logs_h)
                
                elif key == curses.KEY_NPAGE: # Page Down
                    split_y = int(h * 0.6)
                    if state.focused_pane == "list":
                        page_height = max(1, (split_y - 2))
                        state_mgr.move_selection(page_height, page_height)
                    else:
                        detail_h = h - split_y - 1
                        logs_h = max(1, detail_h - 5)
                        state_mgr.scroll_logs(logs_h, logs_h)
                elif key == ord('h') or key == ord('?'): 
                    draw_help_modal(stdscr, h//2, w//2)
                    stdscr.clearok(True)
                    stdscr.refresh()
                elif key == ord('/'): state_mgr.set_filtering(True)
                elif key == 27: state_mgr.set_filter_text("")
                elif key == ord('s') and state.selected_tab == "containers" and not state.bulk_select_mode: 
                    backend.start_container(state_mgr.get_selected_item_id())
                elif key == ord('S'): state_mgr.cycle_sort_mode()
                elif key == ord('P') and not state.bulk_select_mode: backend.prune_all()
                
                elif key in (10, 13): # Enter
                    if state.bulk_select_mode:
                        selected_ids = state_mgr.get_selected_items()
                        action_key = action_menu(stdscr, h//2, w//2, state.selected_tab, None, True)
                        stdscr.clearok(True)
                        stdscr.refresh()
                        if action_key:
                            action_taken = handle_bulk_action(action_key, state.selected_tab, selected_ids, backend, stdscr, state_mgr)
                            if action_taken:
                                list_worker.force_refresh()
                    else:
                        item_id = state_mgr.get_selected_item_id()
                        if item_id:
                            action_key = action_menu(stdscr, h//2, w//2, state.selected_tab, item_id, False)
                            stdscr.clearok(True)
                            stdscr.refresh()
                            if action_key:
                                handle_action(action_key, state.selected_tab, item_id, backend, stdscr, state_mgr, state, list_worker)
                                list_worker.force_refresh()
                
                else:
                    # Handle remaining single-key actions for non-bulk mode
                    item_id = state_mgr.get_selected_item_id()
                    if state.selected_tab == "images" and (key == ord('B') or key == ord('L')):
                        handle_action(chr(key), state.selected_tab, None, backend, stdscr, state_mgr, state, list_worker)
                        continue
                    
                    if item_id and not state.bulk_select_mode:
                         handle_action(chr(key) if 32 <= key <= 126 else key, state.selected_tab, item_id, backend, stdscr, state_mgr, state, list_worker)
             
            except KeyboardInterrupt:
                logging.info("KeyboardInterrupt caught, exiting...")
                break
            except Exception as e:
                logging.error(f"Error in main loop: {e}")
                state_mgr.set_message(f"Error: {e}")
                time.sleep(1) # Prevent tight loop on error
    
    except Exception as e:
         logging.critical(f"Critical error: {e}")
    finally:
         list_worker.running = False
         logs_worker.running = False
         stats_worker.running = False

if __name__ == "__main__":
    import os
    try:
        if os.environ.get("TOCKERDUI_TEST"):
             print("Test mode")
        else:
             curses.wrapper(main)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"Crash: {e}")