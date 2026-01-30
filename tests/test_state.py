import pytest
from tockerdui.state import StateManager
from unittest.mock import MagicMock

class MockContainer:
    def __init__(self, id, name):
        self.id = id
        self.short_id = id[:12] if len(id) > 12 else id
        self.name = name
        self.status = "running"
        self.image = "nginx:latest"
        self.project = ""
        self.cpu_percent = 0
        self.ram_usage = "0MB"
    def __lt__(self, other):
        return self.name < other.name

def test_state_selection():
    sm = StateManager()
    
    # Simulate data
    c_list = []
    for i in [1, 2, 3, 4, 5]:
        m = MockContainer(id=str(i), name=f"c{i}")
        c_list.append(m)
    sm.update_containers(c_list)
    
    # Default index 0
    assert sm.get_snapshot().selected_index == 0
    
    # Move down
    sm.move_selection(1)
    assert sm.get_snapshot().selected_index == 1
    
    # Move past end (clamping)
    sm.move_selection(100)
    assert sm.get_snapshot().selected_index == 4 # index 4 is last element (len 5)
    
    # Move up past 0 (clamping)
    sm.move_selection(-100)
    assert sm.get_snapshot().selected_index == 0

def test_tab_switch_resets_index():
    sm = StateManager()
    sm.update_containers([MockContainer(id=str(i), name=f"c{i}") for i in [1, 2, 3]])
    sm.move_selection(2)
    assert sm.get_snapshot().selected_index == 2
    
    sm.set_tab("images")
    snap = sm.get_snapshot()
    assert snap.selected_tab == "images"
    assert snap.selected_index == 0
