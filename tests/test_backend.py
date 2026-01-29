import pytest
from unittest.mock import MagicMock, patch
from dockterm_raw_v2.backend import DockerBackend
from dockterm_raw_v2.model import ContainerInfo

@pytest.fixture
def mock_docker(mocker):
    # Mock the entire docker module
    mock_client = MagicMock()
    mocker.patch("docker.from_env", return_value=mock_client)
    return mock_client

def test_get_containers(mock_docker):
    # Setup mock container
    c1 = MagicMock()
    c1.id = "long_id_1"
    c1.short_id = "short_1"
    c1.name = "web_server"
    c1.status = "running"
    c1.image.tags = ["nginx:latest"]
    c1.labels = {'com.docker.compose.project': 'my_app'}
    
    c2 = MagicMock()
    c2.id = "long_id_2"
    c2.short_id = "short_2"
    c2.name = "db_server"
    c2.status = "exited"
    c2.image.tags = []
    c2.image.short_id = "sha256:xyz"
    c2.labels = {}

    mock_docker.containers.list.return_value = [c1, c2]

    backend = DockerBackend()
    results = backend.get_containers()

    assert len(results) == 2
    
    assert results[0].name == "web_server"
    assert results[0].project == "my_app"
    assert results[0].image == "nginx:latest"
    
    assert results[1].name == "db_server"
    assert results[1].project == "standalone" # Default value
    assert results[1].image == "sha256:xyz" # Fallback to short_id

def test_get_images(mock_docker):
    i1 = MagicMock()
    i1.id = "img1"
    i1.short_id = "s1"
    i1.tags = ["ubuntu:20.04"]
    i1.attrs = {'Size': 104857600, 'Created': '2023-01-01T12:00:00'} # 100MB

    mock_docker.images.list.return_value = [i1]

    backend = DockerBackend()
    results = backend.get_images()

    assert len(results) == 1
    assert results[0].tags == ["ubuntu:20.04"]
    assert results[0].size_mb == 100.0

def test_container_actions(mock_docker):
    mock_container = MagicMock()
    mock_docker.containers.get.return_value = mock_container

    backend = DockerBackend()
    backend.start_container("123")
    
    mock_docker.containers.get.assert_called_with("123")
    mock_container.start.assert_called_once()
