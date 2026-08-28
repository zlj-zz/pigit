# -*- coding: utf-8 -*-
"""
Module: tests/app/test_bisect.py
Description: BisectSheet, start/reset wiring, and D6 bisect gates.
Author: Zev
Date: 2026-08-28
"""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

from pigit.app import PigitApplication
from pigit.app_bisect import (
    BisectSheet,
    guard_bisect_active,
    parse_bisect_start_input,
)
from pigit.app_branch import BranchPanel
from pigit.app_merge_workflow import MergeWorkflow
from pigit.app_rebase import RebasePanel
from pigit.app_sequencer import SequencerControl
from pigit.config_data import AppConfig
from pigit.git.api import BisectState, GitError
from pigit.git.model import Branch
from pigit.termui import FeedbackKind
from pigit.termui._runtime_context import RuntimeContext, _runtime_ctx, set_overlay_host
from pigit.termui.root import ComponentRoot
from pigit.termui.reactive import Signal
from pigit.viewmodels.branch import IBranchViewModel


@pytest.fixture
def runtime():
    ctx = RuntimeContext()
    token = _runtime_ctx.set(ctx)
    yield ctx
    _runtime_ctx.reset(token)


def _mount(runtime: RuntimeContext) -> tuple[PigitApplication, ComponentRoot]:
    app = PigitApplication(config=AppConfig(repo_observe=False))
    body = app.build_root()
    root = ComponentRoot(
        body,
        runtime.registry,
        event_bus=app._event_bus,
        key_handlers=app._key_handlers,
    )
    runtime.overlay_host = root
    runtime.focus_manager = root._focus_manager
    set_overlay_host(root)
    root._app_on_event = app.on_event
    app._root = root
    app.setup_root(root)
    root.mount()
    root.resize((100, 30))
    return app, root


def _state(
    *,
    good: str = "aaaaaaaaaaaaaaaa",
    bad: str = "bbbbbbbbbbbbbbbb",
    head: str = "ccccccccccccccc",
    steps: int = 4,
) -> BisectState:
    return BisectState(
        good_sha=good,
        bad_sha=bad,
        current_head=head,
        steps_remaining=steps,
    )


def test_parse_bisect_start_input_one_token():
    assert parse_bisect_start_input("v1.0") == ("v1.0", None)


def test_parse_bisect_start_input_two_tokens():
    assert parse_bisect_start_input("v1.0 HEAD") == ("v1.0", "HEAD")


def test_parse_bisect_start_input_rejects_empty_and_extra():
    with pytest.raises(ValueError):
        parse_bisect_start_input("")
    with pytest.raises(ValueError):
        parse_bisect_start_input("a b c")


def test_bisect_sheet_mount_active_shows_status():
    git = Mock()
    git.bisect_status.return_value = _state()
    sheet = BisectSheet(
        git=git,
        on_start=Mock(),
        on_confirm_reset=Mock(),
    )
    sheet.mount()
    text = "\n".join(sheet.content)
    assert "ccccccc" in text
    assert "aaaaaaa" in text
    assert "bbbbbbb" in text
    assert "4 commits remain" in text
    assert "~2 steps to go" in text


def test_bisect_sheet_mount_idle_shows_hint():
    git = Mock()
    git.bisect_status.return_value = None
    sheet = BisectSheet(git=git, on_start=Mock(), on_confirm_reset=Mock())
    sheet.mount()
    text = "\n".join(sheet.content)
    assert "No bisect in progress" in text
    assert "press s to start" in text


def test_bisect_sheet_good_finishes_calls_on_done():
    git = Mock()
    git.bisect_status.side_effect = [_state(), _state(), None]
    done = Mock()
    operated: list[int] = []
    sheet = BisectSheet(
        git=git,
        on_start=Mock(),
        on_confirm_reset=Mock(),
        on_operation=lambda: operated.append(1),
        on_done=done,
    )
    sheet.mount()
    with patch("pigit.app_bisect.show_toast") as toast:
        sheet.good()
    git.bisect_mark_good.assert_called_once()
    done.assert_called_once()
    assert toast.call_args[0][0] == "Bisect finished"
    assert operated == [1]


def test_bisect_sheet_good_refreshes_and_notifies():
    first = _state(head="1111111111111111")
    second = _state(head="3333333333333333", steps=2)
    git = Mock()
    git.bisect_status.side_effect = [first, first, second]
    operated: list[int] = []
    sheet = BisectSheet(
        git=git,
        on_start=Mock(),
        on_confirm_reset=Mock(),
        on_operation=lambda: operated.append(1),
    )
    sheet.mount()
    with patch("pigit.app_bisect.show_toast") as toast:
        sheet.good()
    git.bisect_mark_good.assert_called_once()
    text = "\n".join(sheet.content)
    assert "3333333" in text
    assert "2 commits remain" in text
    assert toast.call_args[0][0] == "Marked good"
    assert operated == [1]


def test_bisect_sheet_mark_git_error_toasts_without_notify():
    git = Mock()
    git.bisect_status.return_value = _state()
    git.bisect_mark_good.side_effect = GitError("no good commit")
    operated: list[int] = []
    sheet = BisectSheet(
        git=git,
        on_start=Mock(),
        on_confirm_reset=Mock(),
        on_operation=lambda: operated.append(1),
    )
    sheet.mount()
    with patch("pigit.app_bisect.show_toast") as toast:
        sheet.good()
    assert toast.call_args[0][0] == "no good commit"
    assert toast.call_args[1].get("kind") == FeedbackKind.ERROR
    assert operated == []


def test_bisect_sheet_refresh_read_error_degrades():
    git = Mock()
    git.bisect_status.side_effect = GitError("interval unresolvable")
    sheet = BisectSheet(git=git, on_start=Mock(), on_confirm_reset=Mock())
    with patch("pigit.app_bisect.show_toast") as toast:
        sheet.mount()
    text = "\n".join(sheet.content)
    assert "unavailable" in text
    assert toast.call_args[0][0] == "Can't read bisect status"


def test_bisect_sheet_mark_guard_read_error_aborts():
    git = Mock()
    git.bisect_status.side_effect = GitError("interval unresolvable")
    sheet = BisectSheet(git=git, on_start=Mock(), on_confirm_reset=Mock())
    with patch("pigit.app_bisect.show_toast"):
        sheet.bad()
    git.bisect_mark_bad.assert_not_called()


def test_bisect_sheet_bad_keeps_session_and_refreshes():
    first = _state(head="1111111111111111", steps=8)
    second = _state(head="2222222222222222", steps=4)
    # mount (1), guard (2), post-mark read (3); _refresh reuses the
    # post-mark state instead of reading a fourth time.
    git = Mock()
    git.bisect_status.side_effect = [first, first, second]
    operated: list[int] = []
    sheet = BisectSheet(
        git=git,
        on_start=Mock(),
        on_confirm_reset=Mock(),
        on_operation=lambda: operated.append(1),
    )
    sheet.mount()
    with patch("pigit.app_bisect.show_toast") as toast:
        sheet.bad()
    git.bisect_mark_bad.assert_called_once()
    text = "\n".join(sheet.content)
    assert "2222222" in text
    assert "4 commits remain" in text
    assert toast.call_args[0][0] == "Marked bad"
    assert operated == [1]


def test_bisect_sheet_good_when_idle_toasts_without_git_call():
    git = Mock()
    git.bisect_status.return_value = None
    sheet = BisectSheet(git=git, on_start=Mock(), on_confirm_reset=Mock())
    sheet.mount()
    with patch("pigit.app_bisect.show_toast") as toast:
        sheet.good()
    git.bisect_mark_good.assert_not_called()
    assert toast.call_args[0][0] == "No bisect in progress"


def test_bisect_sheet_start_and_reset_callbacks():
    started: list[int] = []
    reset: list[int] = []
    git = Mock()
    git.bisect_status.return_value = None
    sheet = BisectSheet(
        git=git,
        on_start=lambda: started.append(1),
        on_confirm_reset=lambda: reset.append(1),
    )
    sheet.start()
    sheet.reset()
    assert started == [1]
    assert reset == [1]


def test_bisect_sheet_close_dismisses():
    git = Mock()
    git.bisect_status.return_value = None
    sheet = BisectSheet(git=git, on_start=Mock(), on_confirm_reset=Mock())
    with patch("pigit.app_bisect.dismiss_sheet") as dismiss:
        sheet.close()
    dismiss.assert_called_once()


def test_open_bisect_sheet_shows_panel(runtime):
    app, _root = _mount(runtime)
    app._git.sequencer_in_progress = Mock(return_value=None)
    app._git.bisect_status = Mock(return_value=None)
    with patch("pigit.app.show_sheet") as show:
        app.open_bisect_sheet()
        show.assert_called_once()
        panel = show.call_args[0][0]
        assert isinstance(panel, BisectSheet)
        app._refresh_git_vms = Mock()
        app._schedule_reload_header = Mock()
        panel._on_operation()
        app._refresh_git_vms.assert_called_once()
        app._schedule_reload_header.assert_called_once()


def test_open_bisect_sheet_blocked_by_sequencer(runtime):
    app, _root = _mount(runtime)
    app._git.sequencer_in_progress = Mock(return_value="merge")
    with (
        patch("pigit.app.show_sheet") as show,
        patch("pigit.app_bisect.show_toast") as toast,
    ):
        app.open_bisect_sheet()
        show.assert_not_called()
        assert "merge" in toast.call_args[0][0]


def test_on_bisect_start_submit_one_and_two_refs(runtime):
    app, _root = _mount(runtime)
    app._git.sequencer_in_progress = Mock(return_value=None)
    app._git.bisect_start = Mock()
    app.open_bisect_sheet = Mock()
    with patch("pigit.app.dismiss_sheet"), patch("pigit.app.show_toast"):
        app._on_bisect_start_submit("v1.0")
    app._git.bisect_start.assert_called_once_with("v1.0", None)
    app.open_bisect_sheet.assert_called_once()

    app._git.bisect_start.reset_mock()
    app.open_bisect_sheet.reset_mock()
    with patch("pigit.app.dismiss_sheet"), patch("pigit.app.show_toast"):
        app._on_bisect_start_submit("v1.0 HEAD~10")
    app._git.bisect_start.assert_called_once_with("v1.0", "HEAD~10")


def test_on_bisect_start_submit_invalid_and_git_error(runtime):
    app, _root = _mount(runtime)
    app._git.sequencer_in_progress = Mock(return_value=None)
    app._git.bisect_start = Mock()
    with patch("pigit.app.show_toast") as toast:
        app._on_bisect_start_submit("a b c")
    app._git.bisect_start.assert_not_called()
    assert "good ref" in toast.call_args[0][0]

    app._git.bisect_start = Mock(side_effect=GitError("bad ref"))
    with patch("pigit.app.show_toast") as toast:
        app._on_bisect_start_submit("v1.0")
    assert toast.call_args[0][0] == "bad ref"
    assert toast.call_args[1].get("kind") == FeedbackKind.ERROR


def test_bisect_start_submit_refreshes_after_success(runtime):
    app, _root = _mount(runtime)
    app._git.sequencer_in_progress = Mock(return_value=None)
    app._git.bisect_start = Mock()
    app.open_bisect_sheet = Mock()
    app._refresh_git_vms = Mock()
    app._schedule_reload_header = Mock()
    with patch("pigit.app.dismiss_sheet"), patch("pigit.app.show_toast"):
        app._on_bisect_start_submit("v1.0")
    app._refresh_git_vms.assert_called_once()
    app._schedule_reload_header.assert_called_once()


def test_confirm_bisect_reset_true_and_false(runtime):
    app, _root = _mount(runtime)
    app._git.bisect_reset = Mock()

    def capture(msg, cb, **_kw):
        cb(False)

    app._alert_dialog.alert = capture
    app._confirm_bisect_reset()
    app._git.bisect_reset.assert_not_called()

    def capture_yes(msg, cb, **_kw):
        cb(True)

    app._alert_dialog.alert = capture_yes
    with patch("pigit.app.dismiss_sheet") as dismiss, patch("pigit.app.show_toast"):
        app._confirm_bisect_reset()
    app._git.bisect_reset.assert_called_once()
    dismiss.assert_called_once()


def test_confirm_bisect_reset_refreshes_after_success(runtime):
    app, _root = _mount(runtime)
    app._git.bisect_reset = Mock()
    app._refresh_git_vms = Mock()
    app._schedule_reload_header = Mock()

    def capture_yes(msg, cb, **_kw):
        cb(True)

    app._alert_dialog.alert = capture_yes
    with patch("pigit.app.dismiss_sheet"), patch("pigit.app.show_toast"):
        app._confirm_bisect_reset()
    app._git.bisect_reset.assert_called_once()
    app._refresh_git_vms.assert_called_once()
    app._schedule_reload_header.assert_called_once()


def test_guard_bisect_active_toasts():
    git = Mock()
    git.bisect_status.return_value = _state()
    with patch("pigit.app_bisect.show_toast") as toast:
        assert guard_bisect_active(git) is True
        assert toast.call_args[0][0] == "A bisect is in progress"
    git.bisect_status.return_value = None
    assert guard_bisect_active(git) is False


def test_can_switch_blocked_during_bisect(runtime):
    app, _root = _mount(runtime)
    app._network_git.busy = False
    app._git.sequencer_in_progress = Mock(return_value=None)
    app._git.bisect_status = Mock(return_value=_state())
    with patch("pigit.app_bisect.show_toast") as toast:
        assert app._can_switch() is False
        assert "bisect" in toast.call_args[0][0].lower()


def test_merge_request_blocked_during_bisect():
    git = Mock()
    git.bisect_status.return_value = _state()
    alert = Mock()
    workflow = MergeWorkflow(
        store=Mock(),
        network=Mock(),
        get_git=lambda: git,
        navigate_product=Mock(),
        get_branch_panel=Mock(),
        get_alert_dialog=lambda: alert,
        get_refresh_git_vms=Mock(),
        get_schedule_reload_header=Mock(),
    )
    with patch("pigit.app_bisect.show_toast"):
        workflow.on_merge_request("feat", "main")
    alert.alert.assert_not_called()


def test_rebase_mount_blocked_during_bisect():
    git = Mock()
    git.sequencer_in_progress.return_value = None
    git.bisect_status.return_value = _state()
    done = Mock()
    panel = RebasePanel(git, "main", on_done=done)
    with patch("pigit.app_bisect.show_toast"):
        panel.mount()
    done.assert_called_once()
    git.list_commits_in_range.assert_not_called()


def test_cherry_pick_blocked_during_bisect():
    git = Mock()
    git.bisect_status.return_value = _state()
    alert = Mock()
    ctrl = SequencerControl(
        get_git=lambda: git,
        get_repo_path=lambda: "/repo",
        navigate_product=Mock(),
        get_alert_dialog=lambda: alert,
        get_refresh_git_vms=Mock(),
        get_refresh_active_panel=Mock(),
    )
    with patch("pigit.app_bisect.show_toast"):
        ctrl.on_cherry_pick("abcdef0", False)
    alert.alert.assert_not_called()
    git.resolve_head_sha.assert_not_called()


def test_branch_checkout_blocked_during_bisect():
    vm = Mock(spec=IBranchViewModel)
    vm.items = Signal([])
    git = Mock()
    git.bisect_status.return_value = _state()
    panel = BranchPanel(vm=vm, get_git=lambda: git)
    panel.branches = [Branch("feat", "0", "0", False)]
    panel.curr_no = 0
    with patch("pigit.app_bisect.show_toast"):
        panel.checkout()
    vm.checkout.assert_not_called()
