"""
tockerdui - A lightweight Terminal User Interface (TUI) for Docker management.

This module provides a curses-based alternative to Docker Desktop with an intuitive
keyboard-driven interface for managing containers, images, volumes, networks, and 
Docker Compose projects.

Features:
  - Multi-tab interface (Containers, Images, Volumes, Networks, Compose)
  - Real-time resource statistics (CPU/RAM)
  - Interactive logging with container shell access
  - Docker Compose project management
  - Optimized rendering (flicker-free updates)
  - Instant filtering and search

Main Components:
  - main.py: Event loop and UI orchestration
  - backend.py: Docker API wrapper
  - state.py: Thread-safe state management and workers
  - ui.py: Curses rendering engine
  - model.py: Data structures (Container, Image, Volume, etc.)

Usage:
  python -m tockerdui

Dependencies:
  - docker>=7.0.0
  - Python 3.10+
  - curses (built-in, not available on Windows natively)
"""

import os
from pathlib import Path

__version__ = "0.1.0"


def get_log_path() -> str:
    """
    Get the log file path following XDG Base Directory spec.
    
    Returns XDG_DATA_HOME/tockerdui/logs/tockerdui.log with fallback to /tmp.
    Creates directory if it doesn't exist.
    
    Returns:
        str: Absolute path to log file (/tmp/tockerdui.log as fallback)
    """
    # Try XDG_DATA_HOME first (Linux/macOS)
    xdg_data_home = os.environ.get('XDG_DATA_HOME')
    if not xdg_data_home:
        # Default fallback: ~/.local/share
        home = Path.home()
        xdg_data_home = home / '.local' / 'share'
    else:
        xdg_data_home = Path(xdg_data_home)
    
    log_dir = xdg_data_home / 'tockerdui' / 'logs'
    
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        return str(log_dir / 'tockerdui.log')
    except (PermissionError, OSError):
        # Fallback to /tmp if permission denied
        return '/tmp/tockerdui.log'
