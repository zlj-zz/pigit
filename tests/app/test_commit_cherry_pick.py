# -*- coding: utf-8 -*-
"""
Module: tests/app/test_commit_cherry_pick.py
Description: Tests for Commit panel cherry-pick emit, help, and app guards.
Author: Zev
Date: 2026-08-19
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from pigit.app import PigitApplication
from pigit.app_commit import CommitPanel
from pigit.config_data import AppConfig
from pigit.git.model import Commit
from pigit.termui import EventType


@pytest.fixture
def app():
    """Create a PigitApplication with mocked git/VMs for cherry-pick."""
    app = PigitApplication(config=AppConfig())
    app._git = MagicMock()
    app._branch_vm = MagicMock()
    app._commit_vm = MagicMock()
    app._status_vm = MagicMock()
    app._tab_view = MagicMock()
    return app


def _auto_confirm(app, *, confirmed: bool = True) -> None:
    """Drive AlertDialog.alert by immediately invoking on_result."""

    def fake_alert(message, on_result, kind=None):
        on_result(confirmed)
        return True

    app._alert_dialog.alert = fake_alert


def test_rejects_commit_already_at_head(app):
    app._git.sequencer_in_progress.return_value = None
    app._git.resolve_head_sha.return_value = "abc"
    with patch("pigit.app.show_toast") as toast, patch("pigit.app.exec_external") as ex:
        app._on_cherry_pick("abc", is_merge=False)
    ex.assert_not_called()
    assert "Already at this commit" in toast.call_args.args[0]


def test_rejects_merge_commit(app):
    app._git.sequencer_in_progress.return_value = None
    app._git.resolve_head_sha.return_value = "head"
    with patch("pigit.app.show_toast") as toast, patch("pigit.app.exec_external") as ex:
        app._on_cherry_pick("other", is_merge=True)
    ex.assert_not_called()
    assert "merge commit" in toast.call_args.args[0]


def test_rejects_revert_in_progress(app):
    app._git.sequencer_in_progress.return_value = "revert"
    with patch("pigit.app.show_toast") as toast, patch("pigit.app.exec_external") as ex:
        app._on_cherry_pick("other", is_merge=False)
    ex.assert_not_called()
    app._git.resolve_head_sha.assert_not_called()
    assert "revert" in toast.call_args.args[0]


def test_cancel_confirm_does_not_run_git(app):
    app._git.sequencer_in_progress.return_value = None
    app._git.resolve_head_sha.return_value = "head"
    _auto_confirm(app, confirmed=False)
    with patch("pigit.app.exec_external") as ex:
        app._on_cherry_pick("deadbeefcafebabe", is_merge=False)
    ex.assert_not_called()


def test_confirm_prompt_uses_short_sha(app):
    app._git.sequencer_in_progress.return_value = None
    app._git.resolve_head_sha.return_value = "head"
    seen = {}

    def fake_alert(message, on_result, kind=None):
        seen["message"] = message
        return True

    app._alert_dialog.alert = fake_alert
    with patch("pigit.app.exec_external"):
        app._on_cherry_pick("deadbeefcafebabe", is_merge=False)
    assert seen["message"] == "Cherry-pick deadbee onto current HEAD?"


def test_success_refreshes_three_vms(app):
    from types import SimpleNamespace

    app._git.sequencer_in_progress.return_value = None
    app._git.resolve_head_sha.return_value = "head"
    _auto_confirm(app, confirmed=True)
    ok = SimpleNamespace(returncode=0)
    with (
        patch("pigit.app.show_badge") as badge,
        patch("pigit.app.exec_external", return_value=ok) as ex,
    ):
        app._on_cherry_pick("deadbeefcafebabe", is_merge=False)
    ex.assert_called_once_with(
        ["git", "cherry-pick", "deadbeefcafebabe"], cwd=app._repo_path
    )
    assert "Cherry-picked deadbee" in badge.call_args.args[0]
    app._status_vm.refresh.assert_called_once()
    app._branch_vm.refresh.assert_called_once()
    app._commit_vm.refresh.assert_called_once()
    app._commit_vm.set_log_ref.assert_not_called()


def test_conflict_routes_to_status(app):
    from types import SimpleNamespace

    app._git.resolve_head_sha.return_value = "head"
    app._git.sequencer_in_progress.side_effect = [None, "cherry-pick"]
    app._git.resolve_head_sha.return_value = "head"
    app._git.has_unmerged_paths.return_value = True
    failed = SimpleNamespace(returncode=1)
    _auto_confirm(app, confirmed=True)
    with (
        patch("pigit.app.show_toast"),
        patch("pigit.app.exec_external", return_value=failed),
    ):
        app._on_cherry_pick("abc", is_merge=False)
    app._tab_view.route_to.assert_called_with("status")


def test_empty_does_not_route_status(app):
    from types import SimpleNamespace

    app._git.resolve_head_sha.return_value = "head"
    app._git.sequencer_in_progress.side_effect = [None, "cherry-pick"]
    app._git.resolve_head_sha.return_value = "head"
    app._git.has_unmerged_paths.return_value = False
    failed = SimpleNamespace(returncode=1)
    _auto_confirm(app, confirmed=True)
    with (
        patch("pigit.app.show_toast") as toast,
        patch("pigit.app.exec_external", return_value=failed),
    ):
        app._on_cherry_pick("abc", is_merge=False)
    assert "skip" in toast.call_args.args[0].lower()
    app._tab_view.route_to.assert_not_called()


def test_on_event_dispatches_cherry_pick(app):
    with patch.object(app, "_on_cherry_pick") as fn:
        app.on_event(
            EventType("action_requested"),
            cmd="cherry-pick",
            sha="abc",
            is_merge=False,
        )
    fn.assert_called_once_with("abc", False)


def test_help_lists_c_not_on_app():
    app = PigitApplication(config=AppConfig())
    app.build_root()
    assert "c" not in {k for k, _ in app.get_help_entries()}
    by_key = {k: d for k, d in app._commit_panel.get_help_entries()}
    assert "c" in by_key
    assert "cherry-pick" in by_key["c"].lower()


def test_cherry_pick_emits_sha_and_merge_flag():
    vm = MagicMock()
    panel = CommitPanel(vm=vm)
    c = Commit(
        sha="abcdef1" + "0" * 33,
        msg="m",
        author="",
        unix_timestamp=0,
        status="",
        extra_info="",
        tag=[],
        parents=["p1", "p2"],
    )
    panel.commits = [c]
    panel.curr_no = 0
    seen = {}

    def fake_emit(action, **data):
        seen["action"] = action
        seen["data"] = data

    panel.emit = fake_emit  # type: ignore
    panel.cherry_pick()
    assert seen["data"]["cmd"] == "cherry-pick"
    assert seen["data"]["sha"] == c.sha
    assert seen["data"]["is_merge"] is True


def test_cherry_pick_silent_when_empty():
    panel = CommitPanel(vm=MagicMock())
    panel.commits = []
    panel.emit = MagicMock()
    panel.cherry_pick()
    panel.emit.assert_not_called()
