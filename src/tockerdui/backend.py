"""
Docker API wrapper and backend operations.

This module provides a high-level interface to Docker operations via the
docker-py library. It abstracts Docker API calls and provides methods for:
  - Fetching and inspecting resources (containers, images, volumes, networks)
  - Executing container actions (start, stop, restart, pause, shell, logs)
  - Managing images (run, pull, build, remove)
  - Managing volumes and networks
  - Monitoring resource usage (CPU, RAM stats)
  - Docker Compose project management

All methods follow a fail-safe pattern: exceptions are caught and logged,
returning empty/default values to prevent UI crashes.

Key Classes:
  - DockerBackend: Main API wrapper with singleton docker.Client

Error Handling:
  - Docker connection errors → return empty collections
  - Permission errors → return empty collections
  - Invalid container/image IDs → return None or empty
  - Shell access failures → fallback to sh, then fail gracefully

Dependencies:
  - docker>=7.0.0 (docker-py client)
  - subprocess (for git operations, shell exec)
  - tarfile (for copy_to_container tar stream)
"""

import docker
import os
import tarfile
import io
import subprocess
import yaml
import resource
import platform
import logging
import functools
from typing import Dict, List, Tuple, Any, Callable, Optional
from .model import ContainerInfo, ImageInfo, VolumeInfo, NetworkInfo, ComposeInfo
from .cache import cached, cache_manager, cache_with_ttl

logger = logging.getLogger(__name__)

def docker_safe(default_return: Any = None) -> Callable:
    """
    Decorator for Docker API methods that ensures safe error handling.
    
    Catches exceptions, logs them, and returns a default value to prevent
    silent failures and UI crashes.
    
    Args:
        default_return: Value to return if exception occurs ([], {}, None, etc.)
    
    Usage:
        @docker_safe(default_return=[])
        def get_containers(self) -> List[ContainerInfo]:
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger.error(f"Docker operation failed in {func.__name__}: {e}", exc_info=True)
                return default_return
        return wrapper
    return decorator



class DockerBackend:
    def __init__(self):
        try:
            self.client = docker.from_env()
        except Exception:
            self.client = None

    @docker_safe(default_return=[])
    @cached(key_prefix="containers")
    def get_containers(self) -> List[ContainerInfo]:
        if not self.client: return []
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

    @docker_safe(default_return="")
    @cached(key_prefix="self_usage")
    def get_self_usage(self) -> str:
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

    @docker_safe(default_return=("--", "--"))
    @cached(key_prefix="container_stats")
    def get_container_stats(self, container_id: str) -> Tuple[str, str]:
        if not self.client: return "--", "--"
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

    @docker_safe(default_return=[])
    @cache_with_ttl(seconds=300, key_prefix="images")
    def get_images(self) -> List[ImageInfo]:
        if not self.client: return []
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

    @docker_safe(default_return=[])
    @cached(key_prefix="volumes")
    def get_volumes(self) -> List[VolumeInfo]:
        if not self.client: return []
        raw = self.client.volumes.list()
        res = []
        for v in raw:
            res.append(VolumeInfo(
                name=v.name,
                driver=v.attrs.get('Driver', 'local'),
                mountpoint=v.attrs.get('Mountpoint', 'n/a')
            ))
        return res

    @docker_safe(default_return=[])
    @cached(key_prefix="networks")
    def get_networks(self) -> List[NetworkInfo]:
        if not self.client: return []
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

    @docker_safe(default_return=[])
    @cached(key_prefix="composes")
    def get_composes(self) -> List[ComposeInfo]:
        containers = []
        if self.client:
            containers = self.client.containers.list(all=True)

        projects: Dict[str, Dict[str, Any]] = {}
        for c in containers:
            p_name = c.labels.get('com.docker.compose.project')
            if p_name:
                if p_name not in projects:
                    projects[p_name] = {"files": c.labels.get('com.docker.compose.project.config_files', 'n/a'), "statuses": []}
                projects[p_name]["statuses"].append(c.status)

        # Merge discovered compose files from filesystem to keep "down" stacks visible.
        discovered = self._discover_compose_projects()
        for name, file_path in discovered.items():
            if name not in projects:
                projects[name] = {"files": file_path, "statuses": []}
            elif projects[name].get("files") in ("", "n/a"):
                projects[name]["files"] = file_path

        res: List[ComposeInfo] = []
        for name, data in projects.items():
            stats = set(data["statuses"])
            if not stats:
                status = "inactive"
            elif len(stats) == 1:
                status = stats.pop()
            else:
                status = "mixed"
            res.append(ComposeInfo(name=name, config_files=data["files"], status=status))
        res.sort(key=lambda c: c.name.lower())
        return res

    def _get_compose_search_paths(self) -> List[str]:
        """Get paths where compose files are discovered."""
        env_paths = os.environ.get("TOCKERDUI_COMPOSE_PATHS", "").strip()
        if env_paths:
            paths = [p for p in env_paths.split(os.pathsep) if p]
        else:
            paths = [os.getcwd()]
        return [os.path.abspath(os.path.expanduser(p)) for p in paths if os.path.isdir(os.path.abspath(os.path.expanduser(p)))]

    def _compose_project_name_from_file(self, compose_file: str) -> str:
        """Resolve project name from compose file `name:` or parent folder."""
        try:
            with open(compose_file, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            if isinstance(data, dict):
                declared = data.get("name")
                if isinstance(declared, str) and declared.strip():
                    return declared.strip()
        except Exception:
            pass
        return os.path.basename(os.path.dirname(compose_file))

    def _discover_compose_projects(self, max_depth: int = 4) -> Dict[str, str]:
        """Discover compose projects from filesystem."""
        compose_names = {
            "docker-compose.yml",
            "docker-compose.yaml",
            "compose.yml",
            "compose.yaml",
        }
        skip_dirs = {
            ".git",
            ".venv",
            "venv",
            "node_modules",
            "__pycache__",
            ".idea",
            ".vscode",
        }

        discovered: Dict[str, str] = {}
        for root in self._get_compose_search_paths():
            for dirpath, dirnames, filenames in os.walk(root):
                rel = os.path.relpath(dirpath, root)
                depth = 0 if rel == "." else rel.count(os.sep) + 1
                if depth > max_depth:
                    dirnames[:] = []
                    continue

                dirnames[:] = [d for d in dirnames if d not in skip_dirs and not d.startswith(".")]

                for file_name in filenames:
                    if file_name not in compose_names:
                        continue
                    file_path = os.path.join(dirpath, file_name)
                    project_name = self._compose_project_name_from_file(file_path)

                    if project_name not in discovered:
                        discovered[project_name] = file_path
                    else:
                        # Collision fallback: keep both with deterministic suffix.
                        suffix = os.path.basename(os.path.dirname(file_path))
                        alt_name = f"{project_name}@{suffix}"
                        if alt_name not in discovered:
                            discovered[alt_name] = file_path
        return discovered

    @docker_safe(default_return=["Docker not connected"])
    def get_logs(self, container_id: str, tail: int = 50) -> List[str]:
        if not self.client: return ["Docker not connected"]
        container = self.client.containers.get(container_id)
        logs_bytes = container.logs(tail=tail)
        return logs_bytes.decode('utf-8', errors='replace').splitlines()

    def get_log_stream_process(self, container_id: str, tail: int = 50) -> subprocess.Popen:
        """Returns a subprocess for streaming logs."""
        cmd = ["docker", "logs", "-f", "--tail", str(tail), container_id]
        return subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,  # Line buffered
            encoding='utf-8',
            errors='replace'
        )

    # Actions
    @docker_safe(default_return=None)
    def start_container(self, container_id: str):
        self.client.containers.get(container_id).start()
        # Invalidate container cache on action
        cache_manager.invalidate("containers")

    @docker_safe(default_return=None)
    def stop_container(self, container_id: str):
        self.client.containers.get(container_id).stop()
        cache_manager.invalidate("containers")
        cache_manager.invalidate_container_stats(container_id)

    @docker_safe(default_return=None)
    def restart_container(self, container_id: str):
        self.client.containers.get(container_id).restart()
        cache_manager.invalidate("containers")
        cache_manager.invalidate_container_stats(container_id)
    
    @docker_safe(default_return=None)
    def pause_container(self, container_id: str):
        self.client.containers.get(container_id).pause()
        cache_manager.invalidate("containers")
        cache_manager.invalidate_container_stats(container_id)

    @docker_safe(default_return=None)
    def unpause_container(self, container_id: str):
        self.client.containers.get(container_id).unpause()
        cache_manager.invalidate("containers")
        cache_manager.invalidate_container_stats(container_id)

    @docker_safe(default_return=None)
    def remove_container(self, container_id: str):
        self.client.containers.get(container_id).remove(force=True)
        cache_manager.invalidate("containers")
        cache_manager.invalidate_container_stats(container_id)

    @docker_safe(default_return=None)
    def rename_container(self, container_id: str, new_name: str):
        if not self.client or not new_name: return
        self.client.containers.get(container_id).rename(new_name)
        cache_manager.invalidate("containers")

    @docker_safe(default_return=None)
    def commit_container(
        self, container_id: str, repository: str, tag: Optional[str] = None
    ):
        if not self.client or not repository: return
        self.client.containers.get(container_id).commit(repository=repository, tag=tag)
        cache_manager.invalidate("images")

    @docker_safe(default_return=None)
    def copy_to_container(self, container_id: str, src_path: str, dest_path: str):
        if not self.client or not src_path or not dest_path: return
        
        # Validate source path (prevent path traversal attacks)
        if src_path.startswith('/') or src_path.startswith('~'):
            logging.warning(f"Rejected copy attempt with absolute/home path: {src_path}")
            return
        
        if '../' in src_path or src_path.startswith('..'):
            logging.warning(f"Rejected copy attempt with path traversal: {src_path}")
            return
        
        src_path = os.path.abspath(os.path.expanduser(src_path))
        
        # Validate that source file exists
        if not os.path.exists(src_path):
            logging.warning(f"Source path does not exist: {src_path}")
            return
        
        # Validate destination path (prevent path traversal in container)
        if dest_path.startswith('~'):
            logging.warning(f"Rejected copy destination with home path: {dest_path}")
            return
        
        if '../' in dest_path or dest_path.startswith('..'):
            logging.warning(f"Rejected copy destination with path traversal: {dest_path}")
            return
        
        c = self.client.containers.get(container_id)
        
        # Create a tar archive of the source
        tar_stream = io.BytesIO()
        with tarfile.open(fileobj=tar_stream, mode='w') as tar:
            tar.add(src_path, arcname=os.path.basename(src_path))
        tar_stream.seek(0)
        
        c.put_archive(path=dest_path, data=tar_stream)
        cache_manager.invalidate("containers")

    def remove_image(self, image_id: str) -> bool:
        if not self.client:
            return False
        try:
            self.client.images.get(image_id).remove(force=True)
            return True
        except Exception as e:
            logger.error(f"Failed to remove image {image_id}: {e}", exc_info=True)
            return False
        finally:
            # Ensure next fetch reflects current Docker state.
            cache_manager.invalidate("images")

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
        cache_manager.invalidate("images")
        
    def build_image(self, path: str, tag: str):
        if not self.client or not path: return
        self.client.images.build(path=path, tag=tag)
        cache_manager.invalidate("images")

    def remove_volume(self, volume_name: str):
        v = self.client.volumes.get(volume_name)
        v.remove(force=True)
        cache_manager.invalidate("volumes")

    def remove_network(self, network_id: str):
        n = self.client.networks.get(network_id)
        n.remove()
        cache_manager.invalidate("networks")

    def prune_all(self):
        if not self.client: return
        self.client.containers.prune()
        self.client.images.prune()
        self.client.volumes.prune()
        self.client.networks.prune()
        cache_manager.invalidate()  # Invalidate all caches as prune affects everything

    def run_container(self, image_id: str, name: Optional[str] = None):
        if not self.client: return
        if name:
            self.client.containers.run(image_id, detach=True, name=name)
        else:
            self.client.containers.run(image_id, detach=True)
        cache_manager.invalidate("containers")

    def create_volume(self, name: str):
        if not self.client: return
        self.client.volumes.create(name=name)
        cache_manager.invalidate("volumes")

    def _get_source_path(self) -> Optional[str]:
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

    def _parse_compose_files(self, config_files: str) -> List[str]:
        if not config_files or config_files == "n/a":
            return []
        parts = [p.strip() for p in config_files.split(",") if p.strip()]
        return parts

    def _build_compose_command(
        self, project_name: str, config_files: str, args: List[str]
    ) -> Tuple[List[str], Optional[str]]:
        cmd = ["docker", "compose", "-p", project_name]
        files = self._parse_compose_files(config_files)
        for path in files:
            cmd.extend(["-f", path])
        cmd.extend(args)
        cwd = None
        if files:
            first_dir = os.path.dirname(files[0])
            if first_dir and os.path.isdir(first_dir):
                cwd = first_dir
        return cmd, cwd

    def check_for_updates(self) -> bool:
        try:
            source_path = self._get_source_path()
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
            return count > 0
        except Exception as e:
            return False

    # --- COMPOSE ACTIONS ---
    
    def compose_up(self, project_name: str, config_files: str = "") -> Tuple[bool, str]:
        """Start services for a Docker Compose project."""
        try:
            cmd, cwd = self._build_compose_command(project_name, config_files, ["up", "-d"])
            result = subprocess.run(cmd, check=False, capture_output=True, text=True, cwd=cwd)
            if result.returncode != 0:
                return False, (result.stderr or result.stdout or "Compose up failed").strip()
            logging.info(f"Compose project '{project_name}' started successfully")
            cache_manager.invalidate("containers")
            cache_manager.invalidate("composes")
            return True, (result.stdout or "Compose started").strip()
        except Exception as e:
            logger.error(f"Compose up failed: {e}", exc_info=True)
            return False, str(e)
    
    def compose_down(self, project_name: str, config_files: str = "") -> Tuple[bool, str]:
        """Stop and remove services for a Docker Compose project."""
        try:
            cmd, cwd = self._build_compose_command(project_name, config_files, ["down"])
            result = subprocess.run(cmd, check=False, capture_output=True, text=True, cwd=cwd)
            if result.returncode != 0:
                return False, (result.stderr or result.stdout or "Compose down failed").strip()
            logging.info(f"Compose project '{project_name}' stopped successfully")
            cache_manager.invalidate("containers")
            cache_manager.invalidate("composes")
            return True, (result.stdout or "Compose stopped").strip()
        except Exception as e:
            logger.error(f"Compose down failed: {e}", exc_info=True)
            return False, str(e)
    
    def compose_remove(self, project_name: str, config_files: str = "") -> Tuple[bool, str]:
        """Remove services, volumes, and networks for a Docker Compose project."""
        try:
            cmd, cwd = self._build_compose_command(project_name, config_files, ["down", "-v"])
            result = subprocess.run(cmd, check=False, capture_output=True, text=True, cwd=cwd)
            if result.returncode != 0:
                return False, (result.stderr or result.stdout or "Compose remove failed").strip()
            logging.info(f"Compose project '{project_name}' removed successfully")
            cache_manager.invalidate("containers")
            cache_manager.invalidate("volumes")
            cache_manager.invalidate("networks")
            cache_manager.invalidate("composes")
            return True, (result.stdout or "Compose removed").strip()
        except Exception as e:
            logger.error(f"Compose remove failed: {e}", exc_info=True)
            return False, str(e)
    
    def compose_pause(self, project_name: str, config_files: str = "") -> Tuple[bool, str]:
        """Pause services for a Docker Compose project."""
        try:
            cmd, cwd = self._build_compose_command(project_name, config_files, ["pause"])
            result = subprocess.run(cmd, check=False, capture_output=True, text=True, cwd=cwd)
            if result.returncode != 0:
                return False, (result.stderr or result.stdout or "Compose pause failed").strip()
            logging.info(f"Compose project '{project_name}' paused successfully")
            cache_manager.invalidate("containers")
            cache_manager.invalidate("composes")
            return True, (result.stdout or "Compose paused").strip()
        except Exception as e:
            logger.error(f"Compose pause failed: {e}", exc_info=True)
            return False, str(e)

    def compose_restart(self, project_name: str, config_files: str = "") -> Tuple[bool, str]:
        """Restart services for a Docker Compose project."""
        try:
            cmd, cwd = self._build_compose_command(project_name, config_files, ["restart"])
            result = subprocess.run(cmd, check=False, capture_output=True, text=True, cwd=cwd)
            if result.returncode != 0:
                return False, (result.stderr or result.stdout or "Compose restart failed").strip()
            logging.info(f"Compose project '{project_name}' restarted successfully")
            cache_manager.invalidate("containers")
            cache_manager.invalidate("composes")
            return True, (result.stdout or "Compose restarted").strip()
        except Exception as e:
            logger.error(f"Compose restart failed: {e}", exc_info=True)
            return False, str(e)

    def compose_pull(self, project_name: str, config_files: str = "") -> Tuple[bool, str]:
        """Pull images for a Docker Compose project."""
        try:
            cmd, cwd = self._build_compose_command(project_name, config_files, ["pull"])
            result = subprocess.run(cmd, check=False, capture_output=True, text=True, cwd=cwd)
            if result.returncode != 0:
                return False, (result.stderr or result.stdout or "Compose pull failed").strip()
            logging.info(f"Compose project '{project_name}' pulled successfully")
            cache_manager.invalidate("images")
            return True, (result.stdout or "Compose pull completed").strip()
        except Exception as e:
            logger.error(f"Compose pull failed: {e}", exc_info=True)
            return False, str(e)

    def perform_update(self):
        try:
            source_path = self._get_source_path()
            if source_path:
                subprocess.call(["./update.sh"], cwd=source_path)
        except Exception:
            pass
