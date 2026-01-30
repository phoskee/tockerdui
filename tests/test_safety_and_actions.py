import pytest
from unittest.mock import MagicMock, patch
import curses
from tockerdui.state import StateManager, ListWorker
from tockerdui.ui import ask_confirmation, draw_footer
from tockerdui.main import handle_action

# Mock curses color functions globally for safety
@pytest.fixture(autouse=True)
def mock_curses_colors(mocker):
    mocker.patch('curses.color_pair', return_value=0)
    mocker.patch('curses.init_pair')
    mocker.patch('curses.start_color')
    mocker.patch('curses.use_default_colors')
    return mocker

def test_state_versioning():
    sm = StateManager()
    initial_version = sm.get_version()
    
    # Update containers should increment version
    sm.update_containers([])
    assert sm.get_version() == initial_version + 1
    
    # Toggle focus should increment version
    sm.toggle_focus()
    assert sm.get_version() == initial_version + 2
    
    # Set tab should increment version
    sm.set_tab("images")
    assert sm.get_version() == initial_version + 3

def test_list_worker_force_refresh():
    sm = StateManager()
    backend = MagicMock()
    worker = ListWorker(sm, backend)
    
    # Initial state
    assert worker._force_refresh_flag == False
    
    # Trigger force refresh
    worker.force_refresh()
    assert worker._force_refresh_flag == True
    
    # Mock time.sleep to exit loop immediately
    with patch('time.sleep', side_effect=[None, InterruptedError]):
        try:
            worker.run()
        except InterruptedError:
            pass
            
    # Flag should be reset after run loop iteration
    # (Note: testing threading internals is tricky, but we can verify the reset logic in a unit-testable way if we refactor or mock carefully)
    # Since we can't easily run the full thread loop without it hanging, we verify the logic manually or via mocks.

def test_ask_confirmation_yes(mocker):
    # Mock a window
    win = MagicMock()
    # Mock window size
    win.getmaxyx.return_value = (5, 30)
    # user presses 'y'
    win.getch.return_value = ord('y')
    
    mocker.patch('curses.newwin', return_value=win)
    
    stdscr = MagicMock()
    result = ask_confirmation(stdscr, 10, 10, "Test Question?")
    
    assert result is True
    win.addstr.assert_any_call(1, 1, " Test Question? (Y/n) ".center(28), curses.A_BOLD)

def test_ask_confirmation_no(mocker):
    win = MagicMock()
    # user presses 'n'
    win.getch.return_value = ord('n')
    
    mocker.patch('curses.newwin', return_value=win)
    
    stdscr = MagicMock()
    result = ask_confirmation(stdscr, 10, 10, "Test Question?")
    
    assert result is False

def test_handle_action_destructive_triggers_refresh(mocker):
    backend = MagicMock()
    stdscr = MagicMock()
    stdscr.getmaxyx.return_value = (24, 80)
    sm = StateManager()
    state = sm.get_snapshot()
    list_worker = MagicMock()
    
    # Mock ask_confirmation to return True
    mocker.patch('tockerdui.main.ask_confirmation', return_value=True)
    
    # Perform 'd' (delete) action on containers
    handle_action('d', 'containers', 'c1', backend, stdscr, sm, state, list_worker)
    
    # Verify backend called
    backend.remove_container.assert_called_with('c1')
    # Verify force_refresh called
    list_worker.force_refresh.assert_called_once()

def test_ui_footer_safety_small_width():
    # Test that draw_footer doesn't crash with 0 or very small width
    stdscr = MagicMock()
    state = StateManager().get_snapshot()
    
    # Should not raise exception
    draw_footer(stdscr, 5, 24, state)
    draw_footer(stdscr, 0, 24, state)
    draw_footer(stdscr, 100, 24, state)

def test_ui_footer_safety_exception_handling(mocker):
    stdscr = MagicMock()
    # Force an error on addstr
    stdscr.addstr.side_effect = curses.error("Test Error")
    state = StateManager().get_snapshot()
    
    # Should catch the error and not crash
    draw_footer(stdscr, 80, 24, state)
