"""
Bulk action handling for tockerdui.
Handles multi-select operations on containers, images, volumes, networks, and compose projects.
"""

import curses
import subprocess
import logging
from typing import Optional, List
from .ui import ask_confirmation, prompt_input

def handle_bulk_action(key: str, tab: str, selected_ids: List[str], backend, 
                     stdscr, state_mgr) -> bool:
    """Handle bulk actions for selected items.
    
    Args:
        key: Action key ('s', 't', 'r', 'd', etc.)
        tab: Current tab ('containers', 'images', etc.)
        selected_ids: List of selected item IDs
        backend: DockerBackend instance
        stdscr: Curses window
        state_mgr: StateManager instance
    
    Returns:
        bool: True if action was taken, False otherwise
    """
    if not selected_ids:
        state_mgr.set_message("No items selected")
        return False
        
    h, w = stdscr.getmaxyx()
    action_taken = False
    
    # --- CONTAINER BULK ACTIONS ---
    if tab == "containers":
        if key == 's':
            # Start all selected containers
            for container_id in selected_ids:
                backend.start_container(container_id)
            state_mgr.set_message(f"Started {len(selected_ids)} containers")
            action_taken = True
            
        elif key == 't':
            # Stop all selected containers
            if ask_confirmation(stdscr, h//2, w//2, f"Stop {len(selected_ids)} containers?"):
                for container_id in selected_ids:
                    backend.stop_container(container_id)
                state_mgr.set_message(f"Stopped {len(selected_ids)} containers")
                action_taken = True
                
        elif key == 'r':
            # Restart all selected containers
            for container_id in selected_ids:
                backend.restart_container(container_id)
            state_mgr.set_message(f"Restarted {len(selected_ids)} containers")
            action_taken = True
            
        elif key == 'd':
            # Remove all selected containers
            if ask_confirmation(stdscr, h//2, w//2, f"Remove {len(selected_ids)} containers?"):
                for container_id in selected_ids:
                    backend.remove_container(container_id)
                state_mgr.set_message(f"Removed {len(selected_ids)} containers")
                action_taken = True
    
    # --- IMAGE BULK ACTIONS ---
    elif tab == "images":
        if key == 'd':
            # Remove all selected images
            if ask_confirmation(stdscr, h//2, w//2, f"Remove {len(selected_ids)} images?"):
                for image_id in selected_ids:
                    backend.remove_image(image_id)
                state_mgr.set_message(f"Removed {len(selected_ids)} images")
                action_taken = True
                
        elif key == 'p':
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
    
    # --- VOLUME BULK ACTIONS ---
    elif tab == "volumes":
        if key == 'd':
            # Remove all selected volumes
            if ask_confirmation(stdscr, h//2, w//2, f"Remove {len(selected_ids)} volumes?"):
                for volume_name in selected_ids:
                    backend.remove_volume(volume_name)
                state_mgr.set_message(f"Removed {len(selected_ids)} volumes")
                action_taken = True
    
    # --- NETWORK BULK ACTIONS ---
    elif tab == "networks":
        if key == 'd':
            # Remove all selected networks
            if ask_confirmation(stdscr, h//2, w//2, f"Remove {len(selected_ids)} networks?"):
                for network_id in selected_ids:
                    backend.remove_network(network_id)
                state_mgr.set_message(f"Removed {len(selected_ids)} networks")
                action_taken = True
    
    # --- COMPOSE BULK ACTIONS ---
    elif tab == "compose":
        if key == 'U':
            # Up all selected compose projects
            for project_name in selected_ids:
                backend.compose_up(project_name)
            state_mgr.set_message(f"Started {len(selected_ids)} compose projects")
            action_taken = True
            
        elif key == 'D':
            # Down all selected compose projects
            if ask_confirmation(stdscr, h//2, w//2, f"Stop {len(selected_ids)} compose projects?"):
                for project_name in selected_ids:
                    backend.compose_down(project_name)
                state_mgr.set_message(f"Stopped {len(selected_ids)} compose projects")
                action_taken = True
                
        elif key == 'r':
            # Remove all selected compose projects
            if ask_confirmation(stdscr, h//2, w//2, f"Remove {len(selected_ids)} compose projects?"):
                for project_name in selected_ids:
                    backend.compose_remove(project_name)
                state_mgr.set_message(f"Removed {len(selected_ids)} compose projects")
                action_taken = True
    
    return action_taken