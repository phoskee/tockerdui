"""
Single-item action handlers for tockerdui.
Refactored from main.py to separate concerns.
"""

import curses
import subprocess
import time
import logging
from typing import Optional, Any
from .ui import ask_confirmation, prompt_input
from .backend import DockerBackend
from .state import StateManager

logger = logging.getLogger(__name__)

def handle_container_action(key: str, item_id: str, backend: DockerBackend, 
                          stdscr, state_mgr: StateManager, state) -> bool:
    """Handle actions for a single container."""
    h, w = stdscr.getmaxyx()
    action_taken = False
    
    if key == 's':
        backend.start_container(item_id)
        action_taken = True
    elif key == 't':
        if ask_confirmation(stdscr, h//2, w//2, "Stop container?"):
             backend.stop_container(item_id)
             action_taken = True
    elif key == 'r':
        backend.restart_container(item_id)
        action_taken = True
    elif key == 'z':
        c_info = next((c for c in state.containers if c.id == item_id), None)
        if c_info:
            if c_info.status == "paused": backend.unpause_container(item_id)
            elif c_info.status == "running": backend.pause_container(item_id)
            action_taken = True
    elif key == 'n':
        new_name = prompt_input(stdscr, h//2, w//2, "New Name: ")
        if new_name: 
            backend.rename_container(item_id, new_name)
            action_taken = True
    elif key == 'k':
        repo = prompt_input(stdscr, h//2, w//2, "Repository: ")
        tag = prompt_input(stdscr, h//2, w//2, "Tag (optional): ")
        if repo: 
            backend.commit_container(item_id, repo, tag if tag else None)
            action_taken = True
    elif key == 'cp':
        src = prompt_input(stdscr, h//2, w//2, "Source Path: ")
        dest = prompt_input(stdscr, h//2, w//2, "Dest Path (in container): ")
        if src and dest: 
            backend.copy_to_container(item_id, src, dest)
            action_taken = True
    elif key == 'x':
        _run_shell_cmd(stdscr, ["docker", "exec", "-it", item_id, "/bin/bash"], fallback_cmd=["docker", "exec", "-it", item_id, "sh"])
    elif key == 'l':
        _run_shell_cmd(stdscr, f"docker logs {item_id} 2>&1 | less -R", shell=True)
    
    return action_taken

def handle_image_action(key: str, item_id: Optional[str], backend: DockerBackend,
                      stdscr, state_mgr: StateManager, state) -> bool:
    """Handle actions for a single image."""
    h, w = stdscr.getmaxyx()
    action_taken = False
    
    # Generic actions that don't need selection or operate on context
    if key == 'B':
        path = prompt_input(stdscr, h//2, w//2, "Path (default .): ")
        if not path: path = "."
        tag = prompt_input(stdscr, h//2, w//2, "Tag (e.g. myimage:latest): ")
        if tag:
             _run_shell_cmd_wait(stdscr, ["docker", "build", "-t", tag, path])
             action_taken = True
        return action_taken
    
    if key == 'L':
        path = prompt_input(stdscr, h//2, w//2, "Load from (e.g. image.tar): ")
        if path: 
            backend.load_image(path)
            action_taken = True
        return action_taken

    # Actions requiring an item
    if not item_id: return False

    if key == 'p':
        img_info = next((i for i in state.images if i.id == item_id), None)
        if img_info and img_info.tags:
            tag = img_info.tags[0]
            if tag != "<none>":
                _run_shell_cmd_wait(stdscr, ["docker", "pull", tag])
                action_taken = True
    elif key == 'R':
        name = prompt_input(stdscr, h // 2, w // 2, "Container Name: ")
        backend.run_container(item_id, name if name else None)
        action_taken = True
    elif key == 'S':
        path = prompt_input(stdscr, h//2, w//2, "Save to (e.g. image.tar): ")
        if path: 
            backend.save_image(item_id, path)
            action_taken = True
    elif key == 'H':
        _run_shell_cmd(stdscr, f"docker history {item_id} | less", shell=True)
        
    return action_taken

def handle_volume_action(key: str, item_id: Optional[str], backend: DockerBackend,
                       stdscr, state_mgr: StateManager) -> bool:
    """Handle actions for volumes."""
    h, w = stdscr.getmaxyx()
    action_taken = False
    
    if key == 'C':
        name = prompt_input(stdscr, h // 2, w // 2, "Volume Name: ")
        if name: 
            backend.create_volume(name)
            action_taken = True
            
    return action_taken

def handle_compose_action(key: str, item_id: str, backend: DockerBackend,
                        stdscr, state_mgr: StateManager, state) -> bool:
    """Handle actions for compose projects."""
    if not item_id: return False
    
    action_taken = False
    comp_info = next((c for c in state.composes if c.name == item_id), None)
    config_files = comp_info.config_files if comp_info else ""

    if key == 'U':
        result = backend.compose_up(item_id, config_files)
        if result is None:
            state_mgr.set_message(f"Compose up failed for '{item_id}'")
        else:
            ok, msg = result
            message = msg if msg else (f"Compose project '{item_id}' is starting..." if ok else f"Compose up failed for '{item_id}'")
            state_mgr.set_message(message)
        action_taken = True
    elif key == 'D':
        result = backend.compose_down(item_id, config_files)
        if result is None:
            state_mgr.set_message(f"Compose down failed for '{item_id}'")
        else:
            ok, msg = result
            message = msg if msg else (f"Compose project '{item_id}' is stopping..." if ok else f"Compose down failed for '{item_id}'")
            state_mgr.set_message(message)
        action_taken = True
    elif key == 'R':
        result = backend.compose_remove(item_id, config_files)
        if result is None:
            state_mgr.set_message(f"Compose remove failed for '{item_id}'")
        else:
            ok, msg = result
            message = msg if msg else (f"Compose project '{item_id}' has been removed..." if ok else f"Compose remove failed for '{item_id}'")
            state_mgr.set_message(message)
        action_taken = True
    elif key == 'P':
        result = backend.compose_pause(item_id, config_files)
        if result is None:
            state_mgr.set_message(f"Compose pause failed for '{item_id}'")
        else:
            ok, msg = result
            message = msg if msg else (f"Compose project '{item_id}' is pausing..." if ok else f"Compose pause failed for '{item_id}'")
            state_mgr.set_message(message)
        action_taken = True
        
    return action_taken

def handle_network_action(key: str, item_id: str, backend: DockerBackend,
                        stdscr, state_mgr: StateManager) -> bool:
    """Handle actions for networks."""
    # Currently networks rely mostly on common actions (inspect/delete)
    # This handler is a placeholder for future specific network actions
    return False

def handle_common_action(key: str, tab: str, item_id: str, backend: DockerBackend,
                       stdscr, state_mgr: StateManager, confirm_fn=ask_confirmation) -> bool:
    """Handle common actions like inspect, delete, prune."""
    h, w = stdscr.getmaxyx()
    action_taken = False
    
    if key == 'i':
        cmd_type = "container"
        if tab == "images": cmd_type = "image"
        elif tab == "volumes": cmd_type = "volume"
        elif tab == "networks": cmd_type = "network"
        _run_shell_cmd(stdscr, f"docker inspect {cmd_type} {item_id} | less", shell=True)
        action_taken = True
        
    elif key == 'd':
        if confirm_fn(stdscr, h//2, w//2, f"Delete {tab[:-1]}?"):
            if tab == "containers": backend.remove_container(item_id)
            elif tab == "images": backend.remove_image(item_id)
            elif tab == "volumes": backend.remove_volume(item_id)
            elif tab == "networks": backend.remove_network(item_id)
            action_taken = True
            
    elif key == 'P':
         if confirm_fn(stdscr, h//2, w//2, "Prune system (all unused)?"):
              _run_shell_cmd_wait(stdscr, None, custom_func=lambda: backend.prune_all(), msg="Pruning system...")
              action_taken = True
              
    return action_taken

# --- Helpers ---

def _run_shell_cmd(stdscr, cmd, shell=False, fallback_cmd=None):
    """Run interactive shell command temporarily suspending curses."""
    curses.def_prog_mode()
    curses.endwin()
    try:
        if isinstance(cmd, str):
            subprocess.call(cmd, shell=shell)
        else:
            subprocess.call(cmd)
    except Exception:
        if fallback_cmd:
            try: subprocess.call(fallback_cmd)
            except: pass
    curses.reset_prog_mode()
    curses.curs_set(0)
    stdscr.nodelay(True)
    stdscr.clearok(True)
    stdscr.refresh()

def _run_shell_cmd_wait(stdscr, cmd, custom_func=None, msg="Working..."):
    """Run shell command or function with wait prompt."""
    curses.def_prog_mode()
    curses.endwin()
    try:
        if custom_func:
            print(msg)
            custom_func()
            print("Done.")
        elif cmd:
            subprocess.call(cmd)
            print("Press Enter to return...")
            input()
    except Exception as e:
        print(f"Error: {e}")
        input()
    curses.reset_prog_mode()
    curses.curs_set(0)
    stdscr.nodelay(True)
    stdscr.clearok(True)
    stdscr.refresh()
