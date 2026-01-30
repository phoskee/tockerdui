import threading
import time
from .model import AppState, ContainerInfo
from .backend import DockerBackend

class StateManager:
    """Thread-safe state manager."""
    def __init__(self):
        self._state = AppState()
        self._lock = threading.Lock()
    
    def update_containers(self, containers):
        with self._lock: 
            stats_map = {c.id: (c.cpu_percent, c.ram_usage) for c in self._state.containers}
            for c in containers:
                if c.id in stats_map:
                    c.cpu_percent, c.ram_usage = stats_map[c.id]
            self._state.containers = containers
    
    def update_container_stats(self, container_id, cpu, ram):
        with self._lock:
            for c in self._state.containers:
                if c.id == container_id:
                    c.cpu_percent = cpu
                    c.ram_usage = ram
                    break

    def update_images(self, images):
        with self._lock: self._state.images = images

    def update_volumes(self, volumes):
        with self._lock: self._state.volumes = volumes

    def update_networks(self, networks):
        with self._lock: self._state.networks = networks
    
    def update_composes(self, composes):
        with self._lock: self._state.composes = composes

    def set_logs(self, logs):
        with self._lock: self._state.logs = logs

    def set_message(self, message: str):
        with self._lock:
            self._state.message = message

    def set_tab(self, tab):
        with self._lock:
            self._state.selected_tab = tab
            self._state.selected_index = 0
            self._state.scroll_offset = 0
            self._state.filter_text = ""
            self._state.is_filtering = False
            self._state.message = "" # Clear message on tab switch

    def set_filtering(self, active: bool):
        with self._lock:
            self._state.is_filtering = active

    def set_filter_text(self, text: str):
        with self._lock:
            self._state.filter_text = text
            current_list = self._get_filtered_list_unlocked(self._state.selected_tab)
            if self._state.selected_index >= len(current_list):
                 self._state.selected_index = max(0, len(current_list) - 1)
    
    def cycle_sort_mode(self):
        with self._lock:
            modes = ["name", "status", "cpu"]
            try:
                idx = modes.index(self._state.sort_mode)
                self._state.sort_mode = modes[(idx + 1) % len(modes)]
            except ValueError:
                self._state.sort_mode = "name"

    def _get_filtered_list_unlocked(self, tab):
        items = []
        if tab == "containers": items = list(self._state.containers)
        elif tab == "images": items = list(self._state.images)
        elif tab == "volumes": items = list(self._state.volumes)
        elif tab == "networks": items = list(self._state.networks)
        elif tab == "compose": items = list(self._state.composes)
        
        if not items: return []

        # Sort items
        if tab == "containers":
            if self._state.sort_mode == "name":
                items.sort(key=lambda x: x.name)
            elif self._state.sort_mode == "status":
                items.sort(key=lambda x: x.status)
            elif self._state.sort_mode == "cpu":
                def get_cpu(x):
                    try: return float(x.cpu_percent.strip('%'))
                    except: return -1.0
                items.sort(key=get_cpu, reverse=True)
        else:
            if hasattr(items[0], 'name'):
                items.sort(key=lambda x: x.name)
            elif hasattr(items[0], 'id'):
                items.sort(key=lambda x: x.id)

        # Filter items
        if not self._state.filter_text:
            return items
            
        ft = self._state.filter_text.lower()
        res = []
        for i in items:
            match = False
            if tab == "containers":
                if ft in i.name.lower() or ft in i.image.lower(): match = True
            elif tab == "images":
                if ft in i.short_id.lower() or any(ft in t.lower() for t in i.tags): match = True
            elif tab == "volumes":
                if ft in i.name.lower(): match = True
            elif tab == "networks":
                if ft in i.name.lower(): match = True
            elif tab == "compose":
                if ft in i.name.lower(): match = True
            
            if match: res.append(i)
        return res

    def move_selection(self, delta, page_height=None):
        with self._lock:
            current_list = self._get_filtered_list_unlocked(self._state.selected_tab)
            current_list_len = len(current_list)
            
            if current_list_len > 0:
                new_idx = self._state.selected_index + delta
                self._state.selected_index = max(0, min(new_idx, current_list_len - 1))
                
                if page_height:
                    if self._state.selected_index < self._state.scroll_offset:
                        self._state.scroll_offset = self._state.selected_index
                    elif self._state.selected_index >= self._state.scroll_offset + page_height:
                        self._state.scroll_offset = self._state.selected_index - page_height + 1
            else:
                 self._state.selected_index = 0

    def get_snapshot(self) -> AppState:
        with self._lock:
            f_containers = self._get_filtered_list_unlocked("containers")
            f_images = self._get_filtered_list_unlocked("images")
            f_volumes = self._get_filtered_list_unlocked("volumes")
            f_networks = self._get_filtered_list_unlocked("networks")
            f_composes = self._get_filtered_list_unlocked("compose")
            
            return AppState(
                containers=[ContainerInfo(c.id, c.short_id, c.name, c.status, c.image, c.project, c.cpu_percent, c.ram_usage) for c in f_containers],
                images=list(f_images),
                volumes=list(f_volumes),
                networks=list(f_networks),
                composes=list(f_composes),
                selected_tab=self._state.selected_tab,
                selected_index=self._state.selected_index,
                scroll_offset=self._state.scroll_offset,
                logs=list(self._state.logs),
                message=self._state.message,
                filter_text=self._state.filter_text,
                is_filtering=self._state.is_filtering,

                sort_mode=self._state.sort_mode,
                update_available=self._state.update_available
            )
    
    def set_update_available(self, available: bool):
        with self._lock:
            self._state.update_available = available

    def get_selected_item_id(self):
        with self._lock:
            current_list = self._get_filtered_list_unlocked(self._state.selected_tab)
            idx = self._state.selected_index
            if idx < len(current_list):
                item = current_list[idx]
                if self._state.selected_tab == "containers": return item.id
                elif self._state.selected_tab == "images": return item.id
                elif self._state.selected_tab == "volumes": return item.name
                elif self._state.selected_tab == "networks": return item.id
                elif self._state.selected_tab == "compose": return item.name
        return None

class BackgroundWorker(threading.Thread):
    def __init__(self, state_manager: StateManager, backend: DockerBackend):
        super().__init__(daemon=True)
        self.state_manager = state_manager
        self.backend = backend
        self.running = True

    def run(self):
        counter = 0
        # Check updates once at startup
        if self.backend.check_for_updates():
            self.state_manager.set_update_available(True)

        while self.running:
            try:
                # Fast loop (1s): Containers always
                containers = self.backend.get_containers()
                self.state_manager.update_containers(containers)
                
                # Slow loop (5s): Images, Volumes, Networks, Composes
                if counter % 5 == 0:
                    self.state_manager.update_images(self.backend.get_images())
                    self.state_manager.update_volumes(self.backend.get_volumes())
                    self.state_manager.update_networks(self.backend.get_networks())
                    self.state_manager.update_composes(self.backend.get_composes())
                
                if counter % 2 == 0:
                    for c in containers:
                        if c.status == "running":
                            cpu, ram = self.backend.get_container_stats(c.id)
                            self.state_manager.update_container_stats(c.id, cpu, ram)
                
                snapshot = self.state_manager.get_snapshot()
                if snapshot.selected_tab == "containers":
                    cid = self.state_manager.get_selected_item_id()
                    if cid:
                        logs = self.backend.get_logs(cid, tail=20)
                        self.state_manager.set_logs(logs)
                
            except Exception:
                pass
            
            counter += 1
            time.sleep(1.0)