import curses
import time
import subprocess
import os
import logging

# Setup logging
logging.basicConfig(filename='/tmp/tockerdui.log', level=logging.DEBUG, 
                    format='%(asctime)s - %(levelname)s - %(message)s')

from .backend import DockerBackend
from .state import StateManager, BackgroundWorker
from .ui import init_colors, draw_header, draw_list, draw_details, draw_footer, prompt_input, draw_help_modal, action_menu

def handle_action(key, tab, item_id, backend, stdscr, state_mgr, state):
    try:
        h, w = stdscr.getmaxyx()
        logging.debug(f"Handling action {key} for tab {tab}")
        
        # --- CONTAINER ACTIONS ---
        if key == 's' and tab == "containers":
            backend.start_container(item_id)
        elif key == 't' and tab == "containers":
            backend.stop_container(item_id)
        elif key == 'r' and tab == "containers":
            backend.restart_container(item_id)
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
        
        # --- COMMON ---
        elif key == 'i':
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
        elif key == 'd':
            if tab == "containers": backend.remove_container(item_id)
            elif tab == "images": backend.remove_image(item_id)
            elif tab == "volumes": backend.remove_volume(item_id)
            elif tab == "networks": backend.remove_network(item_id)
        
        # --- IMAGE ACTIONS ---
        elif key == 'p' and tab == "images":
            img_info = next((i for i in state.images if i.id == item_id), None)
            if img_info and img_info.tags:
                tag = img_info.tags[0]
                if tag != "<none>":
                    curses.def_prog_mode()
                    curses.endwin()
                    try:
                        subprocess.call(["docker", "pull", tag])
                        print("\nPress Enter to return...")
                        input()
                    except Exception: pass
                    curses.reset_prog_mode()
                    curses.curs_set(0)
                    stdscr.nodelay(True)
                    stdscr.clearok(True)
                    stdscr.refresh()
        elif key == 'R' and tab == "images":
            name = prompt_input(stdscr, h // 2, w // 2, "Container Name: ")
            backend.run_container(item_id, name if name else None)
        elif key == 'S' and tab == "images":
            path = prompt_input(stdscr, h//2, w//2, "Save to (e.g. image.tar): ")
            if path: backend.save_image(item_id, path)
        elif key == 'L' and tab == "images":
            path = prompt_input(stdscr, h//2, w//2, "Load from (e.g. image.tar): ")
            if path: backend.load_image(path)
        elif key == 'H' and tab == "images":
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
        elif key == 'B' and tab == "images":
            path = prompt_input(stdscr, h//2, w//2, "Path (default .): ")
            if not path: path = "."
            tag = prompt_input(stdscr, h//2, w//2, "Tag (e.g. myimage:latest): ")
            if tag:
                 curses.def_prog_mode()
                 curses.endwin()
                 try:
                     subprocess.call(["docker", "build", "-t", tag, path])
                     print("\nPress Enter to return...")
                     input()
                 except Exception: pass
                 curses.reset_prog_mode()
                 curses.curs_set(0)
                 stdscr.nodelay(True)
                 stdscr.clearok(True)
                 stdscr.refresh()

        elif key == 'C' and tab == "volumes":
            name = prompt_input(stdscr, h // 2, w // 2, "Volume Name: ")
            if name: backend.create_volume(name)
        
        # --- COMPOSE ACTIONS ---
        elif tab == "compose":
            curses.def_prog_mode()
            curses.endwin()
            try:
                if key == 'U': subprocess.call(["docker", "compose", "-p", item_id, "up", "-d"])
                elif key == 'D': subprocess.call(["docker", "compose", "-p", item_id, "down"])
                elif key == 'r': subprocess.call(["docker", "compose", "-p", item_id, "restart"])
                elif key == 'P': subprocess.call(["docker", "compose", "-p", item_id, "pull"])
                print("\nPress Enter to return...")
                input()
            except Exception: pass
            curses.reset_prog_mode()
            curses.curs_set(0)
            stdscr.nodelay(True)
            stdscr.clearok(True)
            stdscr.refresh()
    except Exception as e:
        logging.error(f"Error in handle_action: {e}", exc_info=True)
        state_mgr.set_message(f"Error: {str(e)}")

def main(stdscr):
    logging.info("Main started")
    try:
        curses.curs_set(0)
        stdscr.nodelay(True)
        stdscr.timeout(100)
        init_colors()
        
        backend = DockerBackend()
        state_mgr = StateManager()
        worker = BackgroundWorker(state_mgr, backend)
        worker.start()
        logging.info("Backend and Worker initialized")

        list_win = None
        detail_win = None
        last_h, last_w = -1, -1

        while True:
            try:
                state = state_mgr.get_snapshot()
                h, w = stdscr.getmaxyx()
                
                if h != last_h or w != last_w:
                    logging.info(f"Resize or init: {h}x{w}")
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
                if list_win: draw_list(list_win, state)
                if detail_win: draw_details(detail_win, state)
                
                curses.doupdate()

                key = stdscr.getch()
                if key == curses.ERR: continue
                
                if state.is_filtering:
                    if key == 27: state_mgr.set_filtering(False)
                    elif key in (10, 13): state_mgr.set_filtering(False)
                    elif key in (curses.KEY_BACKSPACE, 127):
                        state_mgr.set_filter_text(state.filter_text[:-1])
                    elif 32 <= key <= 126:
                        state_mgr.set_filter_text(state.filter_text + chr(key))
                    continue

                if key == ord('q'):
                    logging.info("Quitting")
                    worker.running = False
                    break
                elif key == curses.KEY_F1: state_mgr.set_tab("containers")
                elif key == curses.KEY_F2: state_mgr.set_tab("images")
                elif key == curses.KEY_F3: state_mgr.set_tab("volumes")
                elif key == curses.KEY_F4: state_mgr.set_tab("networks")
                elif key == curses.KEY_F5: state_mgr.set_tab("compose")
                elif key in (ord('h'), ord('?')): 
                    draw_help_modal(stdscr, h//2, w//2)
                    stdscr.clearok(True)
                    stdscr.refresh()
                elif key == curses.KEY_UP: 
                    split_y = int(h * 0.6)
                    page_height = max(1, (split_y - 2) - 3)
                    state_mgr.move_selection(-1, page_height)
                elif key == curses.KEY_DOWN: 
                    split_y = int(h * 0.6)
                    page_height = max(1, (split_y - 2) - 3)
                    state_mgr.move_selection(1, page_height)
                elif key == ord('/'): state_mgr.set_filtering(True)
                elif key == 27: state_mgr.set_filter_text("")
                elif key == ord('S') and state.selected_tab == "containers": state_mgr.cycle_sort_mode()
                elif key == ord('P'): backend.prune_all()
                
                elif key in (10, 13): # Enter
                    item_id = state_mgr.get_selected_item_id()
                    if item_id:
                        action_key = action_menu(stdscr, h//2, w//2, state.selected_tab, item_id)
                        stdscr.clearok(True)
                        stdscr.refresh()
                        if action_key:
                            handle_action(action_key, state.selected_tab, item_id, backend, stdscr, state_mgr, state)
                
                else:
                    item_id = state_mgr.get_selected_item_id()
                    if state.selected_tab == "images" and (key == ord('B') or key == ord('L')):
                        handle_action(chr(key), state.selected_tab, None, backend, stdscr, state_mgr, state)
                        continue
                    
                    if item_id:
                        try:
                            # Only handle alphanumeric actions if it's a valid char
                            if 32 <= key <= 126:
                                handle_action(chr(key), state.selected_tab, item_id, backend, stdscr, state_mgr, state)
                        except: pass

            except Exception as e:
                logging.error(f"Error in main loop: {e}", exc_info=True)
                time.sleep(1) # Prevent tight loop on error

    except Exception as e:
        logging.critical(f"Critical error in main: {e}", exc_info=True)

if __name__ == "__main__":
    curses.wrapper(main)