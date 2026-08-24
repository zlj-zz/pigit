# -*- coding: utf-8 -*-
"""
Module: tests/app/test_network_sync.py
Description: Tests for app-global async push/pull.
Author: Zev
Date: 2026-08-21
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from pigit.app import PigitApplication
from pigit.app_network_git import NetworkGitOutcome
from pigit.config_data import AppConfig
from pigit.git.api import GitError
from pigit.termui import FeedbackKind, ToastPosition


@pytest.fixture
def app():
    application = PigitApplication(config=AppConfig())
    application._git = MagicMock()
    application._git.get_git_dir.return_value = "/tmp/.git"
    application._branch_vm = MagicMock()
    application._commit_vm = MagicMock()
    application._status_vm = MagicMock()
    application._tab_view = MagicMock()
    application._tab_view.route_to.return_value = None
    application._branch_panel = MagicMock()
    application._palette = MagicMock()
    application._palette.is_active = False
    application._network_sync_task = MagicMock()
    return application


def test_busy_guard_blocks_second_sync(app):
    app._network_sync_busy = True
    with (
        patch("pigit.app_network_git.show_toast") as toast,
        patch("pigit.app_network_git.show_spinner") as spin,
    ):
        app._run_network_git("push")
    spin.assert_not_called()
    app._network_sync_task.start.assert_not_called()
    assert "already in progress" in toast.call_args.args[0].lower()


def test_run_network_git_starts_worker_with_center_spinner(app):
    with (
        patch("pigit.app_network_git.dismiss_sheet") as dismiss,
        patch("pigit.app_network_git.show_spinner") as spin,
        patch("pigit.app_network_git.hide_spinner"),
        patch("pigit.app_network_git.show_toast"),
    ):
        app._run_network_git("push")
    dismiss.assert_called_once()
    spin.assert_called_once()
    assert spin.call_args.kwargs.get("position") is ToastPosition.CENTER
    assert app._network_sync_busy is True
    app._network_sync_task.start.assert_called_once()
    work, _done = app._network_sync_task.start.call_args.args
    app._git.push.side_effect = None
    assert work().ok is True
    app._git.push.assert_called_once()


def test_done_success_refreshes_and_clears_busy(app):
    captured = {}

    def fake_start(work, done):
        captured["done"] = done

    app._network_sync_task.start.side_effect = fake_start
    with (
        patch("pigit.app_network_git.dismiss_sheet"),
        patch("pigit.app_network_git.show_spinner"),
        patch("pigit.app_network_git.hide_spinner") as hide,
        patch("pigit.app_network_git.show_toast") as toast,
    ):
        app._run_network_git("pull")
        app._schedule_reload_header = MagicMock()
        app._refresh_git_vms = MagicMock()
        captured["done"](NetworkGitOutcome(ok=True))

    hide.assert_called_once()
    assert app._network_sync_busy is False
    assert toast.call_args.kwargs.get("kind") is FeedbackKind.SUCCESS
    app._refresh_git_vms.assert_called_once()
    app._schedule_reload_header.assert_called_once()


def test_pull_conflict_routes_to_status(app):
    captured = {}

    def fake_start(work, done):
        captured["done"] = done

    app._network_sync_task.start.side_effect = fake_start
    app._git.get_head.return_value = "dev"
    app._merge_state_store.save = MagicMock()
    with (
        patch("pigit.app_network_git.dismiss_sheet"),
        patch("pigit.app_network_git.show_spinner"),
        patch("pigit.app_network_git.hide_spinner"),
        patch("pigit.app_network_git.show_toast") as toast,
    ):
        app._refresh_git_vms = MagicMock()
        app._run_network_git("pull")
        captured["done"](
            NetworkGitOutcome(
                ok=False,
                message="Merge conflict: CONFLICT (content): merge conflict in a.py",
                conflict=True,
            )
        )

    app._tab_view.route_to.assert_called_with("status")
    assert app._merge_state_store.state is not None
    assert app._merge_state_store.state["mode"] == "pull"
    assert app._merge_state_store.state["target"] == "dev"
    app._merge_state_store.save.assert_called_once()
    shown = toast.call_args.args[0]
    assert "CONFLICT" in shown or "conflict" in shown.lower()
    assert "continue-merge" in shown
    assert toast.call_args.kwargs.get("kind") is FeedbackKind.WARNING


def test_continue_merge_pull_mode_commits_without_checkout_back(app):
    app._merge_state_store.set_state(
        {
            "source": "@{upstream}",
            "target": "dev",
            "mode": "pull",
        }
    )
    app._git.is_merge_in_progress.return_value = True
    app._merge_state_store.clear = MagicMock(wraps=app._merge_state_store.clear)
    app._refresh_git_vms = MagicMock()
    app._schedule_reload_header = MagicMock()
    app._confirm_push_and_finish = MagicMock()
    with patch("pigit.app_merge_workflow.show_toast") as toast:
        app._continue_merge()
    app._git.commit_no_edit.assert_called_once()
    app._confirm_push_and_finish.assert_not_called()
    app._git.checkout_branch.assert_not_called()
    app._merge_state_store.clear.assert_called_once()
    assert app._merge_state_store.state is None
    assert toast.call_args.kwargs.get("kind") is FeedbackKind.SUCCESS


def test_work_captures_git_error(app):
    app._git.push.side_effect = GitError("rejected")
    with (
        patch("pigit.app_network_git.dismiss_sheet"),
        patch("pigit.app_network_git.show_spinner"),
        patch("pigit.app_network_git.hide_spinner"),
        patch("pigit.app_network_git.show_toast"),
    ):
        app._run_network_git("push")
    work, _done = app._network_sync_task.start.call_args.args
    outcome = work()
    assert outcome.ok is False
    assert "rejected" in outcome.message


def test_work_captures_non_git_error_so_done_can_clear_busy(app):
    """Non-GitError must become an outcome; AsyncTask would otherwise skip done()."""
    app._git.push.side_effect = RuntimeError("boom")
    with (
        patch("pigit.app_network_git.dismiss_sheet"),
        patch("pigit.app_network_git.show_spinner"),
        patch("pigit.app_network_git.hide_spinner"),
        patch("pigit.app_network_git.show_toast"),
    ):
        app._run_network_git("push")
    work, done = app._network_sync_task.start.call_args.args
    outcome = work()
    assert outcome.ok is False
    assert "boom" in outcome.message
    done(outcome)
    assert app._network_sync_busy is False


def test_merge_push_chains_checkout_on_success(app):
    captured = {}

    def fake_start(work, done):
        captured["done"] = done

    app._network_sync_task.start.side_effect = fake_start

    def fake_alert(message, on_result, kind=None):
        on_result(True)
        return True

    app._alert_dialog.alert = fake_alert
    with (
        patch("pigit.app_network_git.dismiss_sheet"),
        patch("pigit.app_network_git.show_spinner"),
        patch("pigit.app_network_git.hide_spinner"),
        patch("pigit.app_merge_workflow.show_toast"),
    ):
        app._confirm_push_and_finish("main", "feature")
        assert "done" in captured
        app._git.checkout_branch.assert_not_called()
        app._merge_state_store.clear = MagicMock(wraps=app._merge_state_store.clear)
        captured["done"](NetworkGitOutcome(ok=True))

    app._git.checkout_branch.assert_called_once_with("feature")
    app._tab_view.route_to.assert_called_with("branch")


def test_merge_push_still_checkouts_back_on_push_failure(app):
    """Push rejection must not leave the user on target with merge state set."""
    captured = {}

    def fake_start(work, done):
        captured["done"] = done

    app._network_sync_task.start.side_effect = fake_start

    def fake_alert(message, on_result, kind=None):
        on_result(True)
        return True

    app._alert_dialog.alert = fake_alert
    with (
        patch("pigit.app_network_git.dismiss_sheet"),
        patch("pigit.app_network_git.show_spinner"),
        patch("pigit.app_network_git.hide_spinner"),
        patch("pigit.app_network_git.show_toast"),
    ):
        app._confirm_push_and_finish("main", "feature")
        app._merge_state_store.clear = MagicMock(wraps=app._merge_state_store.clear)
        captured["done"](
            NetworkGitOutcome(ok=False, message="rejected (non-fast-forward)")
        )

    app._git.checkout_branch.assert_called_once_with("feature")
    app._merge_state_store.clear.assert_called_once()
    assert app._merge_state_store.state is None


def test_palette_routes_push_to_network_git(app):
    app._run_network_git = MagicMock()
    app._on_palette_execute("push")
    app._run_network_git.assert_called_once_with("push")


def test_palette_fetch_stays_on_run_git_action(app):
    app._run_git_action = MagicMock()
    app._run_network_git = MagicMock()
    app._on_palette_execute("fetch")
    app._run_git_action.assert_called_once_with("fetch")
    app._run_network_git.assert_not_called()
