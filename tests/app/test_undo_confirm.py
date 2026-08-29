# -*- coding: utf-8 -*-
"""
Module: tests/app/test_undo_confirm.py
Description: App-level undo confirm flow — u/U dialogs, rewind, S1 follow-head.
Author: Zev
Date: 2026-08-29
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest

from pigit.app import PigitApplication
from pigit.app_recent_actions import RecentActionsPanel
from pigit.config_data import AppConfig
from pigit.session_history import (
    HistoryRecord,
    ReverseCommand,
    SessionHistory,
    push_rewind,
)


@pytest.fixture
def app():
    """PigitApplication with mocked git; real session history for undo."""
    app = PigitApplication(config=AppConfig())
    app._git = MagicMock()
    app._tab_view = MagicMock()
    app._tab_view.visible = None
    return app


def _auto_confirm(app, *, confirmed: bool = True) -> None:
    """Drive AlertDialog.alert by immediately invoking on_result."""

    def fake_alert(message, on_result, kind=None):
        on_result(confirmed)
        return True

    app._alert_dialog.alert = fake_alert


def _capture_alert(app) -> dict:
    seen = {}

    def fake_alert(message, on_result, kind=None):
        seen["message"] = message
        return True

    app._alert_dialog.alert = fake_alert
    return seen


# ── u: last-action confirm flow ──


def test_u_without_history_toasts_warning(app):
    with patch("pigit.app.show_toast") as toast:
        app.reverse_last_action()
    assert "Nothing to reverse" in toast.call_args.args[0]


def test_u_confirm_dialog_describes_record_and_command(app):
    push_rewind(
        app._session_history, "Merge feat into main", "0123456789abcdef", "Branch"
    )
    seen = _capture_alert(app)
    app.reverse_last_action()
    assert "Undo: Merge feat into main" in seen["message"]
    assert "Run:  git reset --hard 0123456" in seen["message"]


def test_u_confirm_executes_rewind_and_follows_head(app):
    push_rewind(
        app._session_history, "Merge feat into main", "0123456789abcdef", "Branch"
    )
    app._git.status_porcelain.return_value = ""
    _auto_confirm(app, confirmed=True)
    with (
        patch("pigit.app.show_badge") as badge,
        patch("pigit.app.show_toast"),
        patch.object(app, "_on_follow_head") as follow,
        patch.object(app, "_refresh_active_panel"),
    ):
        app.reverse_last_action()
    app._git.hard_reset_head.assert_called_once_with("0123456789abcdef")
    # S1: rewind moves HEAD, so the commit list follows the new checkout.
    follow.assert_called_once()
    assert badge.call_args.args[0] == "Reversed: Merge feat into main"
    assert app._session_history.peek(1) == []


def test_u_cancel_leaves_record_and_head_untouched(app):
    push_rewind(
        app._session_history, "Merge feat into main", "0123456789abcdef", "Branch"
    )
    _auto_confirm(app, confirmed=False)
    with patch("pigit.app.show_toast") as toast:
        app.reverse_last_action()
    app._git.hard_reset_head.assert_not_called()
    assert len(app._session_history.peek(1)) == 1
    toast.assert_not_called()


def test_u_rewind_dirty_guard_toasts_after_confirm(app):
    push_rewind(app._session_history, "Rebase onto main", "abcdef0123456789", "Branch")
    app._git.status_porcelain.return_value = "M f.txt"
    _auto_confirm(app, confirmed=True)
    with (
        patch("pigit.app.show_toast") as toast,
        patch.object(app, "_refresh_active_panel"),
    ):
        app.reverse_last_action()
    app._git.hard_reset_head.assert_not_called()
    assert "uncommitted" in toast.call_args.args[0]


def test_u_commit_undo_regression_requires_confirm(app):
    """Existing commit undo still works, now behind a confirm dialog."""
    app._session_history.push(
        HistoryRecord(
            description="Committed x",
            commands=[ReverseCommand(op_type="commit", payload={})],
            timestamp=time.time(),
            panel_hint="commit",
        )
    )
    _auto_confirm(app, confirmed=True)
    with (
        patch("pigit.app.show_badge"),
        patch.object(app, "_refresh_active_panel"),
        patch.object(app, "_on_follow_head") as follow,
    ):
        app.reverse_last_action()
    app._git.soft_reset_head1.assert_called_once()
    follow.assert_not_called()  # a soft reset does not move HEAD


# ── U: RecentActionsPanel confirm flow ──


def test_confirm_reverse_range_single_record(app):
    push_rewind(
        app._session_history, "Cherry-pick abc1234", "0123456789abcdef", "Branch"
    )
    record = app._session_history.peek(1)[0]
    seen = _capture_alert(app)
    app._confirm_reverse_range([record], lambda: None)
    assert "Undo: Cherry-pick abc1234" in seen["message"]
    assert "Run:  git reset --hard 0123456" in seen["message"]


def test_confirm_reverse_range_multiple_records(app):
    rec_new = HistoryRecord(
        description="Committed x",
        commands=[ReverseCommand(op_type="commit", payload={})],
        timestamp=1.0,
        panel_hint="commit",
    )
    rec_old = HistoryRecord(
        description="Staged a.py",
        commands=[ReverseCommand(op_type="stage", payload={"path": "a.py"})],
        timestamp=0.0,
        panel_hint="status",
    )
    seen = _capture_alert(app)
    app._confirm_reverse_range([rec_new, rec_old], lambda: None)
    assert "Undo 2 actions" in seen["message"]
    assert "- Committed x: git reset --soft HEAD~1" in seen["message"]
    assert "- Staged a.py: git add a.py" in seen["message"]


def test_recent_panel_enter_confirms_range_then_reverses():
    history = SessionHistory()
    history.attach_repo("/repo")
    push_rewind(history, "Merge feat into main", "aa", "Branch")
    push_rewind(history, "Rebase onto main", "bb", "Branch")
    git = MagicMock()
    git.status_porcelain.return_value = ""
    seen = {}

    def confirm(records, do_reverse):
        seen["records"] = records
        seen["do_reverse"] = do_reverse

    panel = RecentActionsPanel(
        history, git, on_done=MagicMock(), confirm_reverse=confirm
    )
    panel.mount()
    panel.curr_no = 0  # newest record
    panel.reverse()
    assert [r.description for r in seen["records"]] == ["Rebase onto main"]
    seen["do_reverse"]()
    git.hard_reset_head.assert_called_once_with("bb")
