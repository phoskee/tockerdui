import pytest
from unittest.mock import MagicMock, patch
import tockerdui.main as app_main
from tockerdui.state import ListWorker

def test_main_loop_init(mocker):
    # Mock curses
    mock_stdscr = MagicMock()
    mock_stdscr.getmaxyx.return_value = (24, 80) # Standard size
    # Simulate pressing 'q', then raise exception to ensure loop breaks if q doesn't work
    mock_stdscr.getch.side_effect = [ord('q'), KeyboardInterrupt]

    mocker.patch('curses.curs_set')
    mocker.patch('curses.start_color')
    mocker.patch('curses.use_default_colors')
    mocker.patch('curses.init_pair')
    mocker.patch('curses.color_pair', return_value=0)
    mocker.patch('curses.doupdate')
    mocker.patch('curses.init_pair')
    
    msg_win_mock = MagicMock()
    msg_win_mock.getmaxyx.return_value = (10, 80)
    msg_win_mock.getch.return_value = -1
    mocker.patch('curses.newwin', return_value=msg_win_mock)

    # Mock Backend to avoid real docker calls
    mocker.patch('curses.newwin', return_value=msg_win_mock)

    # Mock Backend to avoid real docker calls
    mocker.patch('tockerdui.backend.DockerBackend')
    # Mock Workers to avoid threading issues
    mock_list_worker = MagicMock()
    mocker.patch('tockerdui.main.ListWorker', return_value=mock_list_worker)
    mock_logs_worker = MagicMock()
    mocker.patch('tockerdui.main.LogsWorker', return_value=mock_logs_worker)
    mock_stat_worker = MagicMock()
    mocker.patch('tockerdui.main.StatsWorker', return_value=mock_stat_worker)

    # Run main
    app_main.main(mock_stdscr)

    # Verify initialization happened
    mock_stdscr.nodelay.assert_called_with(True)
    mock_stdscr.clear.assert_called()
