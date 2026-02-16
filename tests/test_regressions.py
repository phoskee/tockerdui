from unittest.mock import MagicMock, patch

from tockerdui.model import ContainerInfo
from tockerdui.main_actions import handle_compose_action
from tockerdui.model import ComposeInfo
from tockerdui.state import ListWorker, StateManager


def test_snapshot_includes_bulk_mode_and_error_fields():
    sm = StateManager()
    sm.toggle_bulk_select_mode()
    sm.set_error("boom")

    snap = sm.get_snapshot()
    assert snap.bulk_select_mode is True
    assert snap.last_error == "boom"
    assert snap.error_timestamp > 0


def test_compose_action_remove_accepts_lowercase_r():
    backend = MagicMock()
    backend.compose_remove.return_value = (True, "removed")
    stdscr = MagicMock()
    state_mgr = StateManager()

    state_mgr.update_composes(
        [ComposeInfo(name="proj", config_files="docker-compose.yml", status="running")]
    )
    state = state_mgr.get_snapshot()

    action_taken = handle_compose_action("r", "proj", backend, stdscr, state_mgr, state)

    assert action_taken is True
    backend.compose_remove.assert_called_once_with("proj", "docker-compose.yml")


def test_list_worker_skips_update_check_when_auto_update_disabled():
    sm = StateManager()
    backend = MagicMock()
    backend.get_containers.return_value = []
    backend.get_images.return_value = []
    backend.get_volumes.return_value = []
    backend.get_networks.return_value = []
    backend.get_composes.return_value = []
    backend.check_for_updates.return_value = True

    worker = ListWorker(sm, backend)

    with patch("tockerdui.state.config_manager.should_auto_update", return_value=False):
        with patch("time.sleep", side_effect=InterruptedError):
            try:
                worker.run()
            except InterruptedError:
                pass

    backend.check_for_updates.assert_not_called()


def test_bulk_toggle_container_selection_visible_in_snapshot():
    sm = StateManager()
    sm.update_containers(
        [
            ContainerInfo(
                id="c1",
                short_id="c1",
                name="web",
                status="running",
                image="nginx:latest",
            )
        ]
    )

    sm.toggle_bulk_select_mode()
    sm.toggle_item_selection()

    snap = sm.get_snapshot()
    assert snap.bulk_select_mode is True
    assert len(snap.containers) == 1
    assert snap.containers[0].selected is True
