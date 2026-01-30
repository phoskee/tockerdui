from dataclasses import dataclass, field
from typing import List, Optional

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

@dataclass
class ImageInfo:
    id: str
    short_id: str
    tags: List[str]
    size_mb: float
    created: str

@dataclass
class VolumeInfo:
    name: str
    driver: str
    mountpoint: str

@dataclass
class NetworkInfo:
    id: str
    name: str
    driver: str
    subnet: str

@dataclass
class ComposeInfo:
    name: str
    config_files: str
    status: str # running, exited, mixed

@dataclass
class AppState:
    containers: List[ContainerInfo] = field(default_factory=list)
    images: List[ImageInfo] = field(default_factory=list)
    volumes: List[VolumeInfo] = field(default_factory=list)
    networks: List[NetworkInfo] = field(default_factory=list)
    composes: List[ComposeInfo] = field(default_factory=list)
    selected_tab: str = "containers" # containers, images, volumes, networks, compose
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
