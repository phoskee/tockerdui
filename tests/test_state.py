import pytest
from dockterm_raw_v2.state import StateManager

def test_state_selection():
    sm = StateManager()
    
    # Simulate data
    c_list = [1, 2, 3, 4, 5] # Dummy list
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
    sm.update_containers([1, 2, 3])
    sm.move_selection(2)
    assert sm.get_snapshot().selected_index == 2
    
    sm.set_tab("images")
    snap = sm.get_snapshot()
    assert snap.selected_tab == "images"
    assert snap.selected_index == 0
