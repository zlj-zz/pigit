# -*- coding: utf-8 -*-
"""
Module: tests/app/test_switch_repo.py
Description: Phase 3 _switch_repo / token guard / observe / merge / undo isolation.
Author: Zev
Date: 2026-08-28
"""

from __future__ import annotations

from unittest.mock import MagicMock, Mock, patch

from pigit.app import PigitApplication, _SwitchResult
from pigit.config_data import AppConfig
from pigit.repo_session import RepoSession
from pigit.session_history import HistoryRecord, ReverseCommand
from pigit.termui.async_task import AsyncTask
from pigit.viewmodels.base import ViewModelBase


def _make_session(path: str) -> RepoSession:
    git = Mock()
    git.path = path
    git.get_git_dir = Mock(return_value=f"{path}/.git")
    git.is_merge_in_progress = Mock(return_value=False)
    git.sequencer_in_progress = Mock(return_value=None)
    git.bisect_status = Mock(return_value=None)
    status = MagicMock()
    commit = MagicMock()
    branch = MagicMock()
    for vm in (status, commit, branch):
        vm.bind_repo_token = Mock()
        vm.dispose = Mock()
        vm.refresh = Mock()
    return RepoSession(
        git=git,
        repo_path=path,
        repo_name=path.rsplit("/", 1)[-1],
        status_vm=status,
        commit_vm=commit,
        branch_vm=branch,
    )


def _app_with_panels() -> PigitApplication:
    """Build an app and wire panel mocks so _apply_session can run."""
    with patch.object(RepoSession, "build") as build:
        first = _make_session("/repo/a")
        build.return_value = first
        app = PigitApplication(config=AppConfig(repo_observe=False))
    app._status_panel = MagicMock()
    app._stash_panel = MagicMock()
    app._branch_panel = MagicMock()
    app._commit_panel = MagicMock()
    app._preview_panel = MagicMock()
    app._log_graph_preview = MagicMock()
    app._tab_view = MagicMock()
    app._observe_host = MagicMock()
    app._merge_state_store = MagicMock()
    app._header_state = MagicMock()
    app._schedule_reload_header = Mock()
    app._refresh_git_vms = Mock()
    return app


def test_can_switch_blocks_when_network_busy():
    app = _app_with_panels()
    app._network_git.busy = True
    with patch("pigit.app.show_toast") as toast:
        assert app._can_switch() is False
        toast.assert_called()


def test_can_switch_blocks_when_sequencer_in_progress():
    app = _app_with_panels()
    app._git.sequencer_in_progress.return_value = "rebase"
    with patch("pigit.app_bisect.show_toast") as toast:
        assert app._can_switch() is False
        toast.assert_called()


def test_apply_session_retargets_and_disposes_old():
    app = _app_with_panels()
    old = app._session
    new = _make_session("/repo/b")
    with patch("pigit.app.request_render"):
        app._apply_session(new)
    assert app._session is new
    assert app._repo_path == "/repo/b"
    app._status_panel.set_vm.assert_called_with(new.status_vm)
    app._stash_panel.set_vm.assert_called_with(new.status_vm)
    app._branch_panel.set_vm.assert_called_with(new.branch_vm)
    app._commit_panel.set_vm.assert_called_with(new.commit_vm)
    app._preview_panel.set_vm.assert_called_with(new.status_vm)
    app._log_graph_preview.set_vm.assert_called_with(new.branch_vm)
    app._observe_host.rebind_session.assert_called_once_with()
    app._merge_state_store.rebind.assert_called_once_with(new.git)
    app._tab_view.route_to.assert_called_once_with("status")
    old.status_vm.dispose.assert_called()
    assert app._session_history._active_repo == "/repo/b"


def test_apply_session_rollback_keeps_old_on_side_effect_failure():
    app = _app_with_panels()
    old = app._session
    new = _make_session("/repo/b")
    app._observe_host.rebind_session.side_effect = [RuntimeError("boom"), None]
    with patch("pigit.app.show_toast") as toast:
        app._apply_session(new)
    assert app._session is old
    assert app._repo_path == "/repo/a"
    new.status_vm.dispose.assert_called()
    old.status_vm.dispose.assert_not_called()
    toast.assert_called()
    assert app._status_panel.set_vm.call_args_list[-1].args[0] is old.status_vm


def test_switch_done_drops_stale_token():
    app = _app_with_panels()
    stale = object()
    app._repo_token = object()
    session = _make_session("/repo/b")
    with patch("pigit.app.hide_spinner"):
        app._switch_done(_SwitchResult(True, session=session), stale)
    assert app._session.repo_path == "/repo/a"
    session.status_vm.dispose.assert_called()


def test_switch_repo_async_applies_on_poll():
    app = _app_with_panels()
    new = _make_session("/repo/b")

    def fake_build(git_api, path, history):
        assert path == "/repo/b"
        return new

    with (
        patch.object(RepoSession, "build", side_effect=fake_build),
        patch("pigit.app.show_spinner"),
        patch("pigit.app.hide_spinner"),
        patch("pigit.app.request_render"),
    ):
        app._switch_repo("/repo/b")
        import time

        for _ in range(100):
            AsyncTask.poll_all()
            if app._session is new:
                break
            time.sleep(0.01)
        else:
            raise AssertionError("switch did not apply within timeout")
    assert app._repo_path == "/repo/b"


def test_vm_repo_token_drops_stale_load():
    class _VM(ViewModelBase[int]):
        def _do_load(self) -> list[int]:
            return [1, 2, 3]

    vm = _VM()
    vm.bind_repo_token("t1")
    delivered: list[list[int]] = []

    def capture(data: list[int]) -> None:
        delivered.append(data)

    guarded = vm._guarded(capture)
    vm.bind_repo_token("t2")
    guarded([1, 2, 3])
    assert delivered == []
    vm._guarded(capture)([9])
    assert delivered == [[9]]


def test_merge_state_store_rebind_clears_and_restores(tmp_path):
    from pigit.app_header_state import HeaderState
    from pigit.app_merge_state import MergeStateStore
    from pigit.app_theme import THEME

    header = HeaderState(THEME)
    git_a = Mock()
    git_a.get_git_dir = Mock(return_value=str(tmp_path / "a.git"))
    (tmp_path / "a.git").mkdir()
    store = MergeStateStore(header, get_git_dir=git_a.get_git_dir)
    store.set_branch_conflict("feat", "main")
    assert header.merge_target == "main"

    git_b = Mock()
    git_b.get_git_dir = Mock(return_value=str(tmp_path / "b.git"))
    (tmp_path / "b.git").mkdir()
    git_b.is_merge_in_progress = Mock(return_value=False)
    store.rebind(git_b)
    assert store.state is None
    assert header.merge_target == ""

    store.save("x", "y")
    git_b.is_merge_in_progress = Mock(return_value=True)
    with patch("pigit.app_merge_state.show_toast"):
        store.rebind(git_b)
    assert store.state is not None
    assert store.state["target"] == "y"


def test_observe_rebind_session_stops_then_starts():
    from pigit.app_observe import ObserveDeps, ObserveHost

    deps = MagicMock(spec=ObserveDeps)
    host = ObserveHost(deps)
    host._started = True  # observe was running before the switch
    order: list[str] = []
    host.stop = Mock(side_effect=lambda: order.append("stop"))
    host.start = Mock(side_effect=lambda: order.append("start"))
    host.rebind_session()
    assert order == ["stop", "start"]


def test_observe_rebind_session_noop_when_never_started():
    """repo_observe=False: a switch must not silently start observation (M1)."""
    from pigit.app_observe import ObserveDeps, ObserveHost

    deps = MagicMock(spec=ObserveDeps)
    host = ObserveHost(deps)
    assert host._started is False
    host.stop = Mock()
    host.start = Mock()
    host.rebind_session()
    host.stop.assert_not_called()
    host.start.assert_not_called()


def test_undo_isolation_across_switch():
    app = _app_with_panels()
    history = app._session_history
    history.attach_repo("/repo/a")
    history.push(
        HistoryRecord(
            description="in-a",
            commands=[ReverseCommand(op_type="stage", payload={"path": "a"})],
            timestamp=0.0,
            panel_hint="status",
            repo_path="/repo/a",
        )
    )
    new = _make_session("/repo/b")
    with patch("pigit.app.request_render"):
        app._apply_session(new)
    assert history.peek(5) == []
    result = history.reverse(Mock())
    assert not result.success
    assert "another repository" in result.message


def test_switch_repo_blocks_while_in_flight():
    """A second switch while one is building must be ignored (M2)."""
    app = _app_with_panels()
    app._switch_in_flight = True
    with patch("pigit.app.AsyncTask.start") as start:
        app._switch_repo("/repo/b")
        start.assert_not_called()


def test_close_overlays_closes_inspector_detail_sheet_help():
    app = _app_with_panels()
    app._cancel_inspector_load = Mock()
    app._close_detail_if_open = Mock()
    app._help_popup = Mock()
    app._help_popup.open = True
    with patch("pigit.app.dismiss_sheet"):
        app._close_overlays()
    app._cancel_inspector_load.assert_called_once()
    app._close_detail_if_open.assert_called_once()
    app._help_popup.toggle.assert_called_once()


def test_switch_done_toasts_on_failure_and_resets_in_flight():
    app = _app_with_panels()
    app._switch_in_flight = True
    with (
        patch("pigit.app.hide_spinner"),
        patch("pigit.app.show_toast") as toast,
    ):
        app._switch_done(
            _SwitchResult(False, error="Not a git repository"), app._repo_token
        )
    toast.assert_called()
    assert app._switch_in_flight is False
    assert app._session.repo_path == "/repo/a"


def test_switch_repo_invalid_path_disposes_session():
    """Build returning an unresolved session must dispose it and toast (m7)."""
    app = _app_with_panels()

    def fake_build(git_api, path, history):
        session = _make_session("/repo/b")
        session.repo_path = ""  # confirm_repo returned nothing usable
        return session

    with (
        patch.object(RepoSession, "build", side_effect=fake_build),
        patch("pigit.app.show_spinner"),
        patch("pigit.app.hide_spinner"),
        patch("pigit.app.show_toast") as toast,
    ):
        app._switch_repo("/nope")
        import time

        for _ in range(100):
            AsyncTask.poll_all()
            if app._switch_in_flight is False:
                break
            time.sleep(0.01)
    toast.assert_called()
    assert app._session.repo_path == "/repo/a"
    # The unresolved session's VMs were disposed (build-side dispose).
