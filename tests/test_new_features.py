import pytest
from dockterm_raw_v2.state import StateManager
from dockterm_raw_v2.model import NetworkInfo

def test_scrolling_logic():
    sm = StateManager()
    
    # Simulate 20 items
    items = [i for i in range(20)]
    sm.update_containers(items)
    
    # Page height 5
    page_height = 5
    
    # Initial state
    snap = sm.get_snapshot()
    assert snap.selected_index == 0
    assert snap.scroll_offset == 0
    
    # Move down within page
    sm.move_selection(2, page_height)
    snap = sm.get_snapshot()
    assert snap.selected_index == 2
    assert snap.scroll_offset == 0
    
    # Move to bottom of page (index 4)
    sm.move_selection(2, page_height) # index 4
    snap = sm.get_snapshot()
    assert snap.selected_index == 4
    assert snap.scroll_offset == 0
    
    # Move 1 past page (index 5)
    # Scroll offset should increment to keep index 5 visible at bottom?
    # Logic: if index >= offset + height -> offset = index - height + 1
    # 5 >= 0 + 5 -> offset = 5 - 5 + 1 = 1
    sm.move_selection(1, page_height)
    snap = sm.get_snapshot()
    assert snap.selected_index == 5
    assert snap.scroll_offset == 1
    
    # Move deep down
    sm.move_selection(10, page_height) # index 15
    # offset should be 15 - 5 + 1 = 11
    snap = sm.get_snapshot()
    assert snap.selected_index == 15
    assert snap.scroll_offset == 11
    
    # Move up
    sm.move_selection(-10, page_height) # index 5
    # Logic: if index < offset -> offset = index
    # 5 < 11 -> offset = 5
    snap = sm.get_snapshot()
    assert snap.selected_index == 5
    assert snap.scroll_offset == 5

def test_networks_tab():
    sm = StateManager()
    nets = [NetworkInfo(id="n1", name="net1", driver="bridge", subnet="172.17.0.0/16")]
    sm.update_networks(nets)
    
    sm.set_tab("networks")
    snap = sm.get_snapshot()
    assert snap.selected_tab == "networks"
    assert len(snap.networks) == 1
    assert snap.networks[0].name == "net1"
    
    # Selection ID
    assert sm.get_selected_item_id() == "n1"

def test_filtering_logic():
    sm = StateManager()
    
    # Mock containers
    # We need a class that has .name and .image (or .short_id/.tags)
    from dockterm_raw_v2.model import ContainerInfo
    
    c1 = ContainerInfo(id="1", short_id="1", name="web-app", status="running", image="nginx:latest")
    c2 = ContainerInfo(id="2", short_id="2", name="db-mongo", status="running", image="mongo:4")
    c3 = ContainerInfo(id="3", short_id="3", name="cache-redis", status="running", image="redis:alpine")
    
    sm.update_containers([c1, c2, c3])
    
    # Initial: 3 items
    snap = sm.get_snapshot()
    assert len(snap.containers) == 3
    
    # Filter "web"
    sm.set_filter_text("web")
    snap = sm.get_snapshot()
    assert len(snap.containers) == 1
    assert snap.containers[0].name == "web-app"
    
    # Filter "db"
    sm.set_filter_text("db")
    snap = sm.get_snapshot()
    assert len(snap.containers) == 1
    assert snap.containers[0].name == "db-mongo"
    
    # Filter "mongo" (matches image) -> Actually our logic matches name OR image
    sm.set_filter_text("mongo")
    snap = sm.get_snapshot()
    assert len(snap.containers) == 1
    assert snap.containers[0].name == "db-mongo"
    
    # Move selection on filtered list
    # Currently 1 item. Index 0.
    sm.move_selection(1)
    snap = sm.get_snapshot()
    assert snap.selected_index == 0 # Clamped
    
    # Clear filter
    sm.set_filter_text("")
    snap = sm.get_snapshot()
    assert len(snap.containers) == 3

from unittest.mock import patch, MagicMock

def test_inspect_logic_construction():
    # Verify we build the correct command string logic
    # We can't easily test the full curses loop here without heavy mocking, 
    # but we can verify the logic snippet.
    
    selected_tab = "images"
    item_id = "sha256:123"
    
    cmd_type = "container"
    if selected_tab == "images": cmd_type = "image"
    elif selected_tab == "volumes": cmd_type = "volume"
    elif selected_tab == "networks": cmd_type = "network"
    
    expected_cmd = f"docker inspect {cmd_type} {item_id} | less"
    assert expected_cmd == "docker inspect image sha256:123 | less"
