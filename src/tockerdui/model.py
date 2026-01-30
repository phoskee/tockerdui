"""
Data models and structures for tockerdui application state.

This module defines immutable dataclasses (via @dataclass) that represent
Docker resources and application state. Used throughout the app for:
  - Type safety and IDE autocomplete
  - Clear separation of data (models) from logic (backend/ui/state)
  - Easy serialization/pretty-printing for debugging

Data Classes:
  - ContainerInfo: Docker container metadata (id, name, status, stats)
  - ImageInfo: Docker image metadata (id, tags, size, created)
  - VolumeInfo: Docker volume metadata (name, driver, mount point)
  - NetworkInfo: Docker network metadata (name, driver, scope, subnets)
  - ComposeInfo: Docker Compose project metadata (name, status, services)
  - AppState: Complete application state (all resources + UI selection)

Key Fields:
  - All *Info dataclasses contain Docker resource identifiers and metadata
  - Immutable by default (frozen=True), modified via backend operations
  - Optional fields for data that may not be available
  - String formatting for CPU/RAM stats ("--" if unavailable)

AppState Structure:
  - containers: List[ContainerInfo]
  - images: List[ImageInfo]
  - volumes: List[VolumeInfo]
  - networks: List[NetworkInfo]
  - compose_projects: List[ComposeInfo]
  - selected_tab, selected_index: UI navigation state
  - filter_text, show_inspector: UI display state
  - version: Incremented on state change (for differential rendering)
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

@dataclass
class ContainerInfo:
    id: str
    short_id: str
    name: str
    status: str
    image: str
    project: str = "standalone"
    cpu_percent: str = "--"
    ram_usage: str = "--"
    selected: bool = False  # For bulk selection mode

@dataclass
class ImageInfo:
    id: str
    short_id: str
    tags: List[str]
    size_mb: float
    created: str
    selected: bool = False  # For bulk selection mode

@dataclass
class VolumeInfo:
    name: str
    driver: str
    mountpoint: str
    selected: bool = False  # For bulk selection mode

@dataclass
class NetworkInfo:
    id: str
    name: str
    driver: str
    subnet: str
    selected: bool = False  # For bulk selection mode

@dataclass
class ComposeInfo:
    name: str
    config_files: str
    status: str # running, exited, mixed
    selected: bool = False  # For bulk selection mode

@dataclass
class AppState:
    containers: List[ContainerInfo] = field(default_factory=list)
    images: List[ImageInfo] = field(default_factory=list)
    volumes: List[VolumeInfo] = field(default_factory=list)
    networks: List[NetworkInfo] = field(default_factory=list)
    composes: List[ComposeInfo] = field(default_factory=list)
    selected_tab: str = "containers" # containers, images, volumes, networks, compose, stats
    selected_index: int = 0
    scroll_offset: int = 0
    logs: List[str] = field(default_factory=list)
    message: str = ""
    filter_text: str = ""
    is_filtering: bool = False
    sort_mode: str = "name" # name, status, cpu
    update_available: bool = False
    focused_pane: str = "list" # "list" or "details"
    logs_scroll_offset: int = 0
    self_usage: str = ""
    last_error: str = ""  # Error message to display
    error_timestamp: float = 0.0  # Time when error was set (for auto-clear after 3s)
    bulk_select_mode: bool = False  # Enable bulk selection
    stats_data: dict = field(default_factory=dict)  # Statistics dashboard data
