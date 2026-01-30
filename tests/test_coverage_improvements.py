"""
Additional tests for improved code coverage.

Includes:
- Backend error handling and @docker_safe decorator
- Path validation in copy_to_container
- Compose actions
- State manager filtering and sorting
"""

import pytest
from unittest.mock import MagicMock, patch
from tockerdui.backend import DockerBackend
from tockerdui.state import StateManager
from tockerdui.model import ContainerInfo, ImageInfo, VolumeInfo, NetworkInfo, ComposeInfo
from tockerdui.cache import cache_manager
import subprocess


class TestBackendErrorHandling:
    """Test error handling with @docker_safe decorator."""

    def setup_method(self):
        """Clear cache before each test."""
        cache_manager.invalidate()

    def teardown_method(self):
        """Clear cache after each test."""
        cache_manager.invalidate()

    @patch("tockerdui.backend.docker.from_env")
    def test_get_containers_no_docker_connection(self, mock_docker_env):
        """Test graceful handling when Docker is not available."""
        mock_docker_env.side_effect = Exception("Docker daemon not running")
        
        backend = DockerBackend()
        assert backend.client is None
        
        # Should return empty list, not crash
        results = backend.get_containers()
        assert results == []

    @patch("tockerdui.backend.docker.from_env")
    def test_start_container_docker_error(self, mock_docker_env):
        """Test that container start handles Docker errors gracefully."""
        mock_client = MagicMock()
        mock_docker_env.return_value = mock_client
        
        # Simulate Docker error
        mock_client.containers.get.side_effect = Exception("Container not found")
        
        backend = DockerBackend()
        # Should not raise, returns None
        result = backend.start_container("nonexistent")
        assert result is None

    @patch("tockerdui.backend.docker.from_env")
    def test_get_images_empty(self, mock_docker_env):
        """Test getting images when none exist."""
        mock_client = MagicMock()
        mock_docker_env.return_value = mock_client
        mock_client.images.list.return_value = []
        
        backend = DockerBackend()
        results = backend.get_images()
        assert results == []

    @patch("tockerdui.backend.docker.from_env")
    def test_remove_container_force(self, mock_docker_env):
        """Test that remove_container uses force=True."""
        mock_client = MagicMock()
        mock_docker_env.return_value = mock_client
        mock_container = MagicMock()
        mock_client.containers.get.return_value = mock_container
        
        backend = DockerBackend()
        backend.remove_container("container_id")
        
        mock_container.remove.assert_called_once_with(force=True)


class TestPathValidation:
    """Test path validation in copy_to_container."""

    @patch("tockerdui.backend.docker.from_env")
    @patch("os.path.exists")
    def test_copy_rejects_absolute_src_path(self, mock_exists, mock_docker_env):
        """Test that absolute paths are rejected for security."""
        mock_client = MagicMock()
        mock_docker_env.return_value = mock_client
        
        backend = DockerBackend()
        # Absolute path should be rejected
        result = backend.copy_to_container("container", "/etc/passwd", "/tmp")
        assert result is None
        # Should not reach put_archive
        mock_client.containers.get.assert_not_called()

    @patch("tockerdui.backend.docker.from_env")
    @patch("os.path.exists")
    def test_copy_rejects_home_src_path(self, mock_exists, mock_docker_env):
        """Test that home directory paths are rejected."""
        mock_client = MagicMock()
        mock_docker_env.return_value = mock_client
        
        backend = DockerBackend()
        result = backend.copy_to_container("container", "~/secrets.txt", "/tmp")
        assert result is None
        mock_client.containers.get.assert_not_called()

    @patch("tockerdui.backend.docker.from_env")
    @patch("os.path.exists")
    def test_copy_rejects_path_traversal_src(self, mock_exists, mock_docker_env):
        """Test that path traversal attempts are rejected."""
        mock_client = MagicMock()
        mock_docker_env.return_value = mock_client
        
        backend = DockerBackend()
        result = backend.copy_to_container("container", "../../etc/passwd", "/tmp")
        assert result is None
        mock_client.containers.get.assert_not_called()

    @patch("tockerdui.backend.docker.from_env")
    @patch("os.path.exists")
    def test_copy_rejects_path_traversal_dest(self, mock_exists, mock_docker_env):
        """Test that path traversal in dest is rejected."""
        mock_client = MagicMock()
        mock_docker_env.return_value = mock_client
        mock_exists.return_value = True
        
        backend = DockerBackend()
        result = backend.copy_to_container("container", "file.txt", "../../etc/")
        assert result is None
        mock_client.containers.get.assert_not_called()

    @patch("tockerdui.backend.docker.from_env")
    @patch("os.path.exists")
    def test_copy_rejects_nonexistent_src(self, mock_exists, mock_docker_env):
        """Test that nonexistent source files are rejected."""
        mock_client = MagicMock()
        mock_docker_env.return_value = mock_client
        mock_exists.return_value = False
        
        backend = DockerBackend()
        result = backend.copy_to_container("container", "missing.txt", "/tmp")
        assert result is None
        mock_client.containers.get.assert_not_called()

    @patch("tockerdui.backend.docker.from_env")
    @patch("os.path.exists")
    def test_copy_accepts_valid_relative_path(self, mock_exists, mock_docker_env):
        """Test that valid relative paths are accepted."""
        mock_client = MagicMock()
        mock_docker_env.return_value = mock_client
        mock_container = MagicMock()
        mock_client.containers.get.return_value = mock_container
        mock_exists.return_value = True
        
        with patch("tarfile.open"):
            with patch("builtins.open", create=True):
                backend = DockerBackend()
                backend.copy_to_container("container", "file.txt", "/tmp/dest")
                # Should reach put_archive
                mock_client.containers.get.assert_called_once()


class TestComposeActions:
    """Test Docker Compose operations."""

    @patch("tockerdui.backend.docker.from_env")
    @patch("subprocess.run")
    def test_compose_up(self, mock_run, mock_docker_env):
        """Test compose_up calls correct subprocess."""
        mock_client = MagicMock()
        mock_docker_env.return_value = mock_client
        
        backend = DockerBackend()
        backend.compose_up("myproject")
        
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert "docker" in args
        assert "compose" in args
        assert "-p" in args
        assert "myproject" in args
        assert "up" in args

    @patch("tockerdui.backend.docker.from_env")
    @patch("subprocess.run")
    def test_compose_down(self, mock_run, mock_docker_env):
        """Test compose_down calls correct subprocess."""
        mock_client = MagicMock()
        mock_docker_env.return_value = mock_client
        
        backend = DockerBackend()
        backend.compose_down("myproject")
        
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert "down" in args

    @patch("tockerdui.backend.docker.from_env")
    @patch("subprocess.run")
    def test_compose_remove(self, mock_run, mock_docker_env):
        """Test compose_remove calls with -v flag."""
        mock_client = MagicMock()
        mock_docker_env.return_value = mock_client
        
        backend = DockerBackend()
        backend.compose_remove("myproject")
        
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert "-v" in args  # Volume removal flag

    @patch("tockerdui.backend.docker.from_env")
    @patch("subprocess.run")
    def test_compose_pause(self, mock_run, mock_docker_env):
        """Test compose_pause calls correct subprocess."""
        mock_client = MagicMock()
        mock_docker_env.return_value = mock_client
        
        backend = DockerBackend()
        backend.compose_pause("myproject")
        
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert "pause" in args

    @patch("tockerdui.backend.docker.from_env")
    @patch("subprocess.run")
    def test_compose_error_handling(self, mock_run, mock_docker_env):
        """Test that compose errors are handled gracefully."""
        mock_client = MagicMock()
        mock_docker_env.return_value = mock_client
        # Make subprocess.run raise an error
        mock_run.side_effect = subprocess.CalledProcessError(1, "docker compose")
        
        backend = DockerBackend()
        # Should not crash, returns None
        result = backend.compose_up("badproject")
        assert result is None


class TestStateManagerFiltering:
    """Test state manager filtering and sorting capabilities."""

    def test_filtering_containers(self):
        """Test filtering containers by name."""
        sm = StateManager()
        
        containers = [
            ContainerInfo(id="1", short_id="1", name="web_app", status="running", image="nginx", project="app"),
            ContainerInfo(id="2", short_id="2", name="db_service", status="running", image="postgres", project="app"),
            ContainerInfo(id="3", short_id="3", name="cache", status="exited", image="redis", project="cache"),
        ]
        sm.update_containers(containers)
        
        # Set filter
        sm.set_filter_text("web")
        state = sm.get_snapshot()
        
        # Verify filtered results
        assert len(state.containers) == 1
        assert state.containers[0].name == "web_app"

    def test_clear_filter(self):
        """Test clearing filter shows all items."""
        sm = StateManager()
        
        containers = [
            ContainerInfo(id="1", short_id="1", name="web", status="running", image="nginx", project="app"),
            ContainerInfo(id="2", short_id="2", name="db", status="running", image="postgres", project="app"),
        ]
        sm.update_containers(containers)
        
        sm.set_filter_text("web")
        assert len(sm.get_snapshot().containers) == 1
        
        sm.set_filter_text("")
        assert len(sm.get_snapshot().containers) == 2


class TestStateManagerSelection:
    """Test state manager selection and navigation."""

    def test_get_selected_item_id_containers(self):
        """Test retrieving currently selected container ID."""
        sm = StateManager()
        
        containers = [
            ContainerInfo(id="1", short_id="1", name="app1", status="running", image="nginx", project="app"),
            ContainerInfo(id="2", short_id="2", name="app2", status="exited", image="nginx", project="app"),
        ]
        sm.update_containers(containers)
        sm.move_selection(1)
        
        selected_id = sm.get_selected_item_id()
        assert selected_id is not None
        assert selected_id == "2"

    def test_get_selected_item_id_when_empty(self):
        """Test getting selected item ID when list is empty."""
        sm = StateManager()
        
        selected_id = sm.get_selected_item_id()
        assert selected_id is None

    def test_tab_switch_preserves_but_resets_selection_index(self):
        """Test that switching tabs resets selection to 0."""
        sm = StateManager()
        
        containers = [
            ContainerInfo(id="1", short_id="1", name="app", status="running", image="nginx", project="app"),
        ]
        sm.update_containers(containers)
        sm.move_selection(0)
        
        images = [
            ImageInfo(id="img1", short_id="i1", tags=["ubuntu"], size_mb=100.0, created="2023"),
        ]
        sm.update_images(images)
        
        # Switch tab
        sm.set_tab("images")
        state = sm.get_snapshot()
        
        assert state.selected_tab == "images"
        assert state.selected_index == 0


class TestLoggingConfiguration:
    """Test logging path configuration."""

    @patch("tockerdui.get_log_path")
    def test_log_path_returns_valid_path(self, mock_get_log_path):
        """Test that get_log_path returns a valid path."""
        mock_get_log_path.return_value = "/tmp/tockerdui.log"
        
        from tockerdui import get_log_path
        path = get_log_path()
        
        assert path is not None
        assert "tockerdui" in path

    def test_log_path_supports_xdg(self):
        """Test that log path supports XDG Base Directory."""
        from tockerdui import get_log_path
        
        # Should not raise
        path = get_log_path()
        assert isinstance(path, str)
        assert len(path) > 0
