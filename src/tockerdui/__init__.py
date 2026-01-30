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

__version__ = "0.1.0"

