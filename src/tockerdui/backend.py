import docker
import os
import tarfile
import io
import subprocess
import resource
import platform
from typing import List, Tuple
from .model import ContainerInfo, ImageInfo, VolumeInfo, NetworkInfo, ComposeInfo

class DockerBackend:
    def __init__(self):
        try:
            self.client = docker.from_env()
        except Exception:
            self.client = None

    def get_containers(self) -> List[ContainerInfo]:
        if not self.client: return []
        try:
            raw = self.client.containers.list(all=True)
            res = []
            for c in raw:
                project = c.labels.get('com.docker.compose.project', 'standalone')
                image_tag = c.image.tags[0] if c.image.tags else (c.image.short_id if c.image.short_id else "unknown")
                res.append(ContainerInfo(
                    id=c.id,
                    short_id=c.short_id,
                    name=c.name,
                    status=c.status,
                    image=image_tag,
                    project=project
                ))
            return res
        except Exception:
            return []

    def get_self_usage(self) -> str:
        try:
            pid = os.getpid()
            
            # MEMORY: Use resource module (more accurate than ps)
            # MacOS returns bytes, Linux returns KB
            usage = resource.getrusage(resource.RUSAGE_SELF)
            rss_val = usage.ru_maxrss
            if platform.system() == 'Darwin':
                rss_mb = rss_val / (1024 * 1024)
            else:
                rss_mb = rss_val / 1024
            
            # CPU: Use ps (best option without psutil)
            cmd = ["ps", "-p", str(pid), "-o", "%cpu"]
            # Output: %CPU \n 0.0
            output = subprocess.check_output(cmd).decode().strip().splitlines()
            cpu = "?"
            if len(output) >= 2:
                cpu = output[1].strip().replace(',', '.') # Handle 0,0
            
            return f"CPU: {cpu}% MEM: {rss_mb:.1f}MB"
        except Exception:
            return ""

    def get_container_stats(self, container_id: str) -> Tuple[str, str]:
        if not self.client: return "--", "--"
        try:
            c = self.client.containers.get(container_id)
            if c.status != 'running': return "0.0%", "0.0MB"
            stats = c.stats(stream=False)
            cpu_stats = stats.get('cpu_stats', {})
            precpu_stats = stats.get('precpu_stats', {})
            cpu_usage = cpu_stats.get('cpu_usage', {}).get('total_usage', 0)
            precpu_usage = precpu_stats.get('cpu_usage', {}).get('total_usage', 0)
            system_cpu_usage = cpu_stats.get('system_cpu_usage', 0)
            presystem_cpu_usage = precpu_stats.get('system_cpu_usage', 0)
            online_cpus = cpu_stats.get('online_cpus', len(cpu_stats.get('cpu_usage', {}).get('percpu_usage', [])) or 1)
            cpu_delta = cpu_usage - precpu_usage
            system_delta = system_cpu_usage - presystem_cpu_usage
            cpu_percent = 0.0
            if system_delta > 0.0 and cpu_delta > 0.0:
                cpu_percent = (cpu_delta / system_delta) * online_cpus * 100.0
            mem_usage_bytes = stats.get('memory_stats', {}).get('usage', 0)
            mem_usage_mb = mem_usage_bytes / (1024 * 1024)
            return f"{cpu_percent:.1f}%", f"{mem_usage_mb:.1f}MB"
        except Exception:
            return "--", "--"

    def get_images(self) -> List[ImageInfo]:
        if not self.client: return []
        try:
            raw = self.client.images.list()
            res = []
            for i in raw:
                tags = i.tags if i.tags else ["<none>"]
                size_mb = i.attrs.get('Size', 0) / (1024 * 1024)
                created = i.attrs.get('Created', '')[:10]
                res.append(ImageInfo(
                    id=i.id,
                    short_id=i.short_id if i.short_id else "sha256:...",
                    tags=tags,
                    size_mb=size_mb,
                    created=created
                ))
            return res
        except Exception:
            return []

    def get_volumes(self) -> List[VolumeInfo]:
        if not self.client: return []
        try:
            raw = self.client.volumes.list()
            res = []
            for v in raw:
                res.append(VolumeInfo(
                    name=v.name,
                    driver=v.attrs.get('Driver', 'local'),
                    mountpoint=v.attrs.get('Mountpoint', 'n/a')
                ))
            return res
        except Exception:
            return []

    def get_networks(self) -> List[NetworkInfo]:
        if not self.client: return []
        try:
            raw = self.client.networks.list()
            res = []
            for n in raw:
                subnet = "n/a"
                if n.attrs.get('IPAM') and n.attrs['IPAM'].get('Config'):
                    configs = n.attrs['IPAM']['Config']
                    if configs and 'Subnet' in configs[0]:
                        subnet = configs[0]['Subnet']
                res.append(NetworkInfo(
                    id=n.id,
                    name=n.name,
                    driver=n.attrs.get('Driver', 'bridge'),
                    subnet=subnet
                ))
            return res
        except Exception:
            return []

    def get_composes(self) -> List[ComposeInfo]:
        if not self.client: return []
        try:
            containers = self.client.containers.list(all=True)
            projects = {}
            for c in containers:
                p_name = c.labels.get('com.docker.compose.project')
                if p_name:
                    if p_name not in projects:
                        projects[p_name] = {"files": c.labels.get('com.docker.compose.project.config_files', 'n/a'), "statuses": []}
                    projects[p_name]["statuses"].append(c.status)
            res = []
            for name, data in projects.items():
                stats = set(data["statuses"])
                if len(stats) == 1: status = stats.pop()
                else: status = "mixed"
                res.append(ComposeInfo(name=name, config_files=data["files"], status=status))
            return res
        except Exception:
            return []

    def get_logs(self, container_id: str, tail: int = 50) -> List[str]:
        if not self.client: return ["Docker not connected"]
        try:
            container = self.client.containers.get(container_id)
            logs_bytes = container.logs(tail=tail)
            return logs_bytes.decode('utf-8', errors='replace').splitlines()
        except Exception as e:
            return [f"Error fetching logs: {str(e)}"]

    # Actions
    def start_container(self, container_id: str):
        self.client.containers.get(container_id).start()

    def stop_container(self, container_id: str):
        self.client.containers.get(container_id).stop()

    def restart_container(self, container_id: str):
        self.client.containers.get(container_id).restart()
    
    def pause_container(self, container_id: str):
        self.client.containers.get(container_id).pause()

    def unpause_container(self, container_id: str):
        self.client.containers.get(container_id).unpause()

    def remove_container(self, container_id: str):
        self.client.containers.get(container_id).remove(force=True)

    def rename_container(self, container_id: str, new_name: str):
        if not self.client or not new_name: return
        self.client.containers.get(container_id).rename(new_name)

    def commit_container(self, container_id: str, repository: str, tag: str = None):
        if not self.client or not repository: return
        self.client.containers.get(container_id).commit(repository=repository, tag=tag)

    def copy_to_container(self, container_id: str, src_path: str, dest_path: str):
        if not self.client or not src_path or not dest_path: return
        c = self.client.containers.get(container_id)
        
        # Create a tar archive of the source
        tar_stream = io.BytesIO()
        with tarfile.open(fileobj=tar_stream, mode='w') as tar:
            tar.add(src_path, arcname=os.path.basename(src_path))
        tar_stream.seek(0)
        
        c.put_archive(path=dest_path, data=tar_stream)

    def remove_image(self, image_id: str):
        if not self.client: return
        try:
            self.client.images.get(image_id).remove(force=True)
        except: pass

    def save_image(self, image_id: str, file_path: str):
        if not self.client or not file_path: return
        image = self.client.images.get(image_id)
        with open(file_path, 'wb') as f:
            for chunk in image.save():
                f.write(chunk)

    def load_image(self, file_path: str):
        if not self.client or not file_path: return
        with open(file_path, 'rb') as f:
            self.client.images.load(f)
        
    def build_image(self, path: str, tag: str):
        if not self.client or not path: return
        self.client.images.build(path=path, tag=tag)

    def remove_volume(self, volume_name: str):
        v = self.client.volumes.get(volume_name)
        v.remove(force=True)

    def remove_network(self, network_id: str):
        n = self.client.networks.get(network_id)
        n.remove()

    def prune_all(self):
        if not self.client: return
        self.client.containers.prune()
        self.client.images.prune()
        self.client.volumes.prune()
        self.client.networks.prune()

    def run_container(self, image_id: str, name: str = None):
        if not self.client: return
        if name:
            self.client.containers.run(image_id, detach=True, name=name)
        else:
            self.client.containers.run(image_id, detach=True)

    def create_volume(self, name: str):
        if not self.client: return
        self.client.volumes.create(name=name)

    def _get_source_path(self) -> str:
        try:
            # Assuming installed at $INSTALL_DIR/tockerdui/backend.py
            # We want $INSTALL_DIR/source_path
            install_dir = os.path.dirname(os.path.dirname(__file__))
            source_path_file = os.path.join(install_dir, "source_path")
            
            if os.path.exists(source_path_file):
                with open(source_path_file, 'r') as f:
                    path = f.read().strip()
                    if os.path.isdir(path):
                        return path
            
            # Fallback: maybe we are running from source? check for .git in parent of package
            # package is src/tockerdui. parent is src. parent of parent is root.
            possible_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            if os.path.exists(os.path.join(possible_root, ".git")):
                return possible_root
                
            return None
        except Exception:
            return None

    def check_for_updates(self) -> bool:
        try:
            source_path = self._get_source_path()
            with open("/tmp/tockerdui_debug.log", "a") as f:
                 f.write(f"Source path: {source_path}\n")
            
            if not source_path: return False
            
            # Fetch remote
            subprocess.check_call(["git", "fetch"], cwd=source_path, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            # Check for INCOMING changes (origin/main ahead of HEAD)
            # HEAD..origin/main
            output = subprocess.check_output(
                ["git", "rev-list", "HEAD..origin/main", "--count"], 
                cwd=source_path
            )
            count = int(output.decode('utf-8').strip())
            
            with open("/tmp/tockerdui_debug.log", "a") as f:
                 f.write(f"Git count: {count}\n")
            
            return count > 0
        except Exception as e:
            with open("/tmp/tockerdui_debug.log", "a") as f:
                 f.write(f"Update check error: {e}\n")
            return False

    def perform_update(self):
        try:
            source_path = self._get_source_path()
            if source_path:
                subprocess.call(["./update.sh"], cwd=source_path)
        except Exception:
            pass