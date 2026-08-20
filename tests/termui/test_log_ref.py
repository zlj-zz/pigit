# -*- coding: utf-8 -*-
"""
Module: tests/termui/test_log_ref.py
Description: LogRefSheet and commit log-ref app wiring.
Author: Zev
Date: 2026-08-19
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from pigit.app import PigitApplication
from pigit.app_branch import BranchPanel
from pigit.app_commit import CommitPanel
from pigit.app_log_ref import LogRefSheet
from pigit.config_data import AppConfig
from pigit.git.model import Branch
from pigit.termui import EventType, FeedbackKind
from pigit.viewmodels.base import ActionResult


def _sheet(names=None, current="HEAD", on_pick=None, on_done=None):
    return LogRefSheet(
        names=names or ["HEAD", "main", "origin/foo"],
        current_ref=current,
        on_pick=on_pick or MagicMock(),
        on_done=on_done or MagicMock(),
    )


def test_activate_puts_head_first_and_cursors_current():
    panel = _sheet(current="origin/foo")
    panel.activate()
    assert panel.content == ["HEAD", "main", "origin/foo"]
    assert panel.curr_no == 2


def test_filter_narrows_and_enter_picks_mapped():
    pick = MagicMock()
    done = MagicMock()
    panel = _sheet(on_pick=pick, on_done=done)
    panel.activate()
    panel._search_query = "foo"
    panel._sync_filter()
    panel.curr_no = 0
    panel.confirm()
    pick.assert_called_once_with("origin/foo")
    done.assert_called_once()


def test_enter_noop_when_filter_empty():
    pick = MagicMock()
    panel = _sheet(on_pick=pick)
    panel.activate()
    panel._search_query = "zzzz"
    panel._sync_filter()
    panel.confirm()
    pick.assert_not_called()


def test_esc_closes_without_pick():
    pick = MagicMock()
    done = MagicMock()
    panel = _sheet(on_pick=pick, on_done=done)
    panel.activate()
    panel.close()
    pick.assert_not_called()
    done.assert_called_once()


def test_enter_confirms_even_with_filter_active():
    """Enter confirms the selection instead of only exiting the filter."""
    from pigit.termui import keys

    pick = MagicMock()
    done = MagicMock()
    panel = _sheet(on_pick=pick, on_done=done)
    panel.activate()
    panel.enter_search()
    panel._search_query = "foo"
    panel._sync_filter()
    panel.curr_no = 0
    assert panel.capture_key(keys.KEY_ENTER) is True
    pick.assert_called_once_with("origin/foo")
    done.assert_called_once()


def test_describe_row_marks_cursor_and_current_ref():
    panel = _sheet(current="origin/foo")
    panel.activate()
    left, main, _right = panel.describe_row(2, True)
    assert panel.CURSOR in "".join(s.text for s in left)
    assert "origin/foo" in "".join(s.text for s in main)
    _, _, right = panel.describe_row(2, True)
    assert any("current" in s.text for s in right)
    left_other, _, _ = panel.describe_row(0, False)
    assert panel.CURSOR not in "".join(s.text for s in left_other)


@pytest.fixture
def app():
    app = PigitApplication(config=AppConfig())
    app._git = MagicMock()
    app._commit_vm = MagicMock()
    app._commit_panel = MagicMock()
    app._tab_view = MagicMock()
    return app


def test_show_log_sets_ref_routes_and_toasts_when_pinned(app):
    app._commit_vm.viewing_checkout_log.return_value = False
    with patch("pigit.app.show_toast") as toast:
        app.on_event(EventType("action_requested"), cmd="show-log", ref="origin/foo")
    app._commit_vm.set_log_ref.assert_called_once_with("origin/foo")
    app._tab_view.route_to.assert_called_once_with("commit")
    assert toast.call_args.args[0] == "Showing log: origin/foo"
    assert toast.call_args.kwargs["kind"] is FeedbackKind.INFO


def test_show_log_no_toast_when_viewing_checkout(app):
    app._commit_vm.viewing_checkout_log.return_value = True
    with patch("pigit.app.show_toast") as toast:
        app.on_event(EventType("action_requested"), cmd="show-log", ref="main")
    app._tab_view.route_to.assert_called_once_with("commit")
    toast.assert_not_called()


def test_show_log_routes_even_when_ref_invalid(app):
    """Ref validation moved to the async load; show-log always routes."""
    with patch("pigit.app.show_toast"):
        app.on_event(EventType("action_requested"), cmd="show-log", ref="nope")
    app._commit_vm.set_log_ref.assert_called_once_with("nope")
    app._tab_view.route_to.assert_called_once_with("commit")


def test_follow_head_sets_ref_without_route(app):
    app._commit_vm.follow_head.return_value = False
    with patch("pigit.app.show_toast") as toast:
        app.on_event(EventType("action_requested"), cmd="follow-head", ref="feat")
    app._commit_vm.follow_head.assert_called_once_with("feat")
    app._tab_view.route_to.assert_not_called()
    toast.assert_not_called()


def test_help_title_pinned():
    vm = MagicMock()
    vm.viewing_checkout_log.return_value = False
    vm.log_ref = "origin/foo"
    panel = CommitPanel(vm=vm)
    assert panel.get_help_title() == "Commit · origin/foo"


def test_help_title_checkout():
    vm = MagicMock()
    vm.viewing_checkout_log.return_value = True
    vm.log_ref = "main"
    panel = CommitPanel(vm=vm)
    assert panel.get_help_title() == "Commit"


def test_tab_name_tracks_help_title():
    vm = MagicMock()
    vm.viewing_checkout_log.return_value = False
    vm.log_ref = "origin/foo"
    panel = CommitPanel(vm=vm)
    assert panel.tab_name == "Commit · origin/foo"
    assert panel.tab_key == "4"


def test_help_lists_o():
    built = PigitApplication(config=AppConfig())
    built.build_root()
    by_key = {k: d for k, d in built._commit_panel.get_help_entries()}
    assert "o" in by_key
    assert by_key["o"] == "Show log of another ref"


def test_open_log_ref_shows_sheet():
    vm = MagicMock()
    vm.log_ref = "HEAD"
    vm.list_log_ref_names.return_value = ["HEAD", "main"]
    panel = CommitPanel(vm=vm)
    with (
        patch("pigit.app_commit.show_sheet") as sheet,
        patch("pigit.app_commit.terminal_size", return_value=(80, 24)),
    ):
        panel.open_log_ref()
    sheet.assert_called_once()
    child = sheet.call_args.args[0]
    assert isinstance(child, LogRefSheet)


def test_on_pick_sets_ref_and_toasts():
    vm = MagicMock()
    vm.viewing_checkout_log.return_value = False
    vm.log_ref = "HEAD"
    vm.list_log_ref_names.return_value = ["HEAD", "feat"]
    panel = CommitPanel(vm=vm)
    captured = {}

    def fake_sheet(child, **kwargs):
        captured["sheet"] = child

    with (
        patch("pigit.app_commit.show_sheet", fake_sheet),
        patch("pigit.app_commit.terminal_size", return_value=(80, 24)),
        patch("pigit.app_commit.show_toast") as toast,
    ):
        panel.open_log_ref()
        captured["sheet"]._on_pick("feat")
    vm.set_log_ref.assert_called_once_with("feat")
    assert toast.call_args.args[0] == "Showing log: feat"


def _br(name, is_head=False, is_remote=False):
    return Branch(name, "?", "?", is_head, is_remote=is_remote)


def test_enter_emits_show_log():
    vm = MagicMock()
    panel = BranchPanel(vm=vm)
    panel.branches = [_br("origin/foo", is_remote=True)]
    panel.curr_no = 0
    seen = {}

    def fake_emit(action, **data):
        seen["data"] = data

    panel.emit = fake_emit
    panel.show_log()
    assert seen["data"]["cmd"] == "show-log"
    assert seen["data"]["ref"] == "origin/foo"


def test_enter_silent_when_empty():
    panel = BranchPanel(vm=MagicMock())
    panel.branches = []
    panel.emit = MagicMock()
    panel.show_log()
    panel.emit.assert_not_called()


def test_checkout_success_emits_follow_head():
    vm = MagicMock()
    vm.checkout.return_value = ActionResult(True, "ok", True)
    panel = BranchPanel(vm=vm)
    panel.branches = [_br("feat")]
    panel.curr_no = 0
    seen = []

    def fake_emit(action, **data):
        seen.append(data)

    panel.emit = fake_emit
    with patch("pigit.app_branch.show_badge"):
        panel.checkout()
    assert {"cmd": "follow-head", "ref": "feat"} in seen


def test_checkout_failure_no_follow_head():
    vm = MagicMock()
    vm.checkout.return_value = ActionResult(False, "no", False)
    panel = BranchPanel(vm=vm)
    panel.branches = [_br("feat")]
    panel.curr_no = 0
    panel.emit = MagicMock()
    with patch("pigit.app_branch.show_toast"):
        panel.checkout()
    panel.emit.assert_not_called()


def test_branch_help_enter():
    built = PigitApplication(config=AppConfig())
    built.build_root()
    by_key = {k: d for k, d in built._branch_panel.get_help_entries()}
    assert "Enter" in by_key
    assert by_key["Enter"] == "Show commits (no checkout)"
    assert "checkout" in by_key["c"].lower()
