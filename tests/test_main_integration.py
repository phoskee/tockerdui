import pytest
from unittest.mock import MagicMock, patch
import dockterm_raw_v2.main as app_main

def test_main_loop_init(mocker):
    # Mock curses
    mock_stdscr = MagicMock()
    mock_stdscr.getmaxyx.return_value = (24, 80) # Standard size
    mock_stdscr.getch.side_effect = [ord('q')] # Simulate pressing 'q' immediately

    mocker.patch('curses.curs_set')
    mocker.patch('curses.start_color')
    mocker.patch('curses.use_default_colors')
    mocker.patch('curses.init_pair')
    mocker.patch('curses.newwin', return_value=MagicMock())

    # Mock Backend to avoid real docker calls
    mocker.patch('dockterm_raw_v2.backend.DockerBackend')

    # Run main
    app_main.main(mock_stdscr)

    # Verify initialization happened
    mock_stdscr.nodelay.assert_called_with(True)
    mock_stdscr.erase.assert_called()
