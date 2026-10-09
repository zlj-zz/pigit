# -*- coding: utf-8 -*-
"""
Module: tests/app/test_network_sync.py
Description: Tests for app-global async push/pull.
Author: Zev
Date: 2026-08-21
"""

from __future__ import annotations

from unittest.mock import MagicMock, Mock, patch

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
    application._git.has_upstream.return_value = True
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
    """A second sync is refused -- but the caller still hears the attempt is
    over, or a merge sequence waiting on the push would hang. The refusal goes
    to the badge, whose slot the running sync's spinner does not share."""
    app._network_sync_busy = True
    done = Mock()
    with (
        patch("pigit.app_network_git.show_badge") as badge,
        patch("pigit.app_network_git.show_toast") as toast,
        patch("pigit.app_network_git.show_spinner") as spin,
    ):
        app._network_git.run("push", on_complete=done)
    spin.assert_not_called()
    app._network_sync_task.start.assert_not_called()
    toast.assert_not_called()
    assert "already in progress" in badge.call_args.args[0].lower()
    done.assert_called_once()


def test_run_network_git_starts_worker_with_center_spinner(app):
    with (
        patch("pigit.app_network_git.dismiss_sheet") as dismiss,
        patch("pigit.app_network_git.show_spinner") as spin,
        patch("pigit.app_network_git.hide_spinner"),
        patch("pigit.app_network_git.show_toast"),
    ):
        app._network_git.run("push")
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
        app._network_git.run("pull")
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
        app._network_git.run("pull")
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
        app._network_git.run("push")
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
        app._network_git.run("push")
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
        app._refresh_git_vms = MagicMock()
        captured["done"](NetworkGitOutcome(ok=True))

    app._git.checkout_branch.assert_called_once_with("feature")
    # The sequence ends where the user is: what they are looking at gets
    # reloaded (the checkout back moved HEAD under it) instead of the flow
    # pulling them over to Branch. Two refreshes run -- the push's own, then
    # this one after the checkout back, which is the one that matters.
    assert app._refresh_git_vms.called
    app._tab_view.route_to.assert_not_called()


def test_a_skipped_push_still_finishes_the_merge_sequence(app):
    """NetworkGit refuses a second sync. The merge sequence asked for this push
    and waits on it, so the refusal has to come back as "the attempt is over" --
    otherwise the flow never checks out back and never clears its state."""
    app._network_sync_busy = True
    app._alert_dialog.alert = lambda message, on_result, kind=None: (
        on_result(True),
        True,
    )[1]
    app._merge_state_store.clear = MagicMock(wraps=app._merge_state_store.clear)
    with (
        patch("pigit.app_network_git.dismiss_sheet"),
        patch("pigit.app_network_git.show_badge") as badge,
        patch("pigit.app_merge_workflow.show_toast") as toast,
    ):
        app._confirm_push_and_finish("main", "feature")

    app._git.push.assert_not_called()
    app._git.checkout_branch.assert_called_once_with("feature")
    assert badge.called, "the skipped push is said out loud"
    app._merge_state_store.clear.assert_called_once()
    assert app._merge_state_store.state is None
    # The merge happened; the push did not. The wording must not imply both.
    assert "Merged into main" in toast.call_args.args[0]
    assert "push" not in toast.call_args.args[0].lower()


def test_a_confirm_that_never_shows_does_not_hang_the_sequence(app):
    """``alert`` returns False without registering the answer when another
    modal is already open. Waiting for an answer that cannot come would leave
    the merge sequence hanging with its state never cleared."""
    app._alert_dialog.alert = lambda message, on_result, kind=None: False
    app._merge_state_store.clear = MagicMock(wraps=app._merge_state_store.clear)
    with (
        patch("pigit.app_merge_workflow.show_toast") as toast,
        patch("pigit.app_merge_workflow.show_badge") as badge,
    ):
        app._confirm_push_and_finish("main", "feature")

    app._git.push.assert_not_called()
    app._git.checkout_branch.assert_called_once_with("feature")
    assert badge.called
    app._merge_state_store.clear.assert_called_once()
    assert app._merge_state_store.state is None
    assert "Merged into main" in toast.call_args.args[0]


def test_finish_merge_checkout_reloads_the_header_after_the_head_move(app):
    """The checkout back moves HEAD to ``source``, and the header reads
    branch/ahead/behind from HEAD. The push's own header reload was scheduled
    before this checkout and races it, so the workflow re-runs it here -- else
    the header keeps the merged-into branch, for good when repo_observe is off.
    """
    app._refresh_git_vms = MagicMock()
    app._schedule_reload_header = MagicMock()
    with patch("pigit.app_merge_workflow.show_toast"):
        app._merge_workflow.finish_merge_checkout("main", "feature")

    app._git.checkout_branch.assert_called_once_with("feature")
    assert app._refresh_git_vms.called
    app._schedule_reload_header.assert_called_once()


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


def test_the_push_action_routes_to_network_git(app):
    """``universal.push`` runs the same method the ``P`` key does."""
    app._network_git = MagicMock()
    app.push_upstream()
    app._network_git.run.assert_called_once_with("push")


def test_the_fetch_action_never_merges(app):
    """``universal.fetch`` is its own action: fetching must not go through the
    network-git path, which is what makes pull and push interactive."""
    app._sequencer = MagicMock()
    app._network_git = MagicMock()
    app.fetch_remote()
    app._sequencer.run_git_action.assert_called_once_with("fetch")
    app._network_git.run.assert_not_called()


def test_push_no_upstream_alert_confirm_runs_set_upstream(app):
    app._git.has_upstream.return_value = False
    app._git.get_current_branch.return_value = "feature/fxk_api_count"
    app._git.default_push_remote.return_value = "origin"
    app._git.push_set_upstream.side_effect = None

    def fake_alert(message, on_result, kind=None):
        assert "feature/fxk_api_count" in message
        assert "git push --set-upstream origin feature/fxk_api_count" in message
        assert kind is FeedbackKind.WARNING
        on_result(True)
        return True

    app._alert_dialog.alert = fake_alert
    with (
        patch("pigit.app_network_git.dismiss_sheet"),
        patch("pigit.app_network_git.show_spinner") as spin,
        patch("pigit.app_network_git.hide_spinner"),
        patch("pigit.app_network_git.show_toast"),
    ):
        app._network_git.run("push")
    spin.assert_called_once()
    work, _done = app._network_sync_task.start.call_args.args
    assert work().ok is True
    app._git.push_set_upstream.assert_called_once_with(
        "origin", "feature/fxk_api_count"
    )
    app._git.push.assert_not_called()


def test_push_no_upstream_alert_cancel_skips_worker(app):
    app._git.has_upstream.return_value = False
    app._git.get_current_branch.return_value = "feature/fxk_api_count"
    app._git.default_push_remote.return_value = "origin"
    completed = []

    def fake_alert(message, on_result, kind=None):
        on_result(False)
        return True

    app._alert_dialog.alert = fake_alert
    with (
        patch("pigit.app_network_git.show_spinner") as spin,
        patch("pigit.app_network_git.show_toast"),
    ):
        app._network_git.run("push", on_complete=lambda: completed.append(True))
    spin.assert_not_called()
    app._network_sync_task.start.assert_not_called()
    assert completed == [True]


def test_push_no_remote_toasts_without_spinner(app):
    app._git.has_upstream.return_value = False
    app._git.get_current_branch.return_value = "dev"
    app._git.default_push_remote.return_value = None
    with (
        patch("pigit.app_network_git.show_spinner") as spin,
        patch("pigit.app_network_git.show_toast") as toast,
    ):
        app._network_git.run("push")
    spin.assert_not_called()
    assert "No remote" in toast.call_args.args[0]
    assert toast.call_args.kwargs.get("kind") is FeedbackKind.WARNING


def test_push_detached_head_toasts_without_spinner(app):
    app._git.has_upstream.return_value = False
    app._git.get_current_branch.return_value = None
    with (
        patch("pigit.app_network_git.show_spinner") as spin,
        patch("pigit.app_network_git.show_toast") as toast,
    ):
        app._network_git.run("push")
    spin.assert_not_called()
    assert "Detached HEAD" in toast.call_args.args[0]


def test_pull_no_upstream_toasts_without_spinner(app):
    app._git.has_upstream.return_value = False
    with (
        patch("pigit.app_network_git.show_spinner") as spin,
        patch("pigit.app_network_git.show_toast") as toast,
    ):
        app._network_git.run("pull")
    spin.assert_not_called()
    app._network_sync_task.start.assert_not_called()
    assert "No upstream" in toast.call_args.args[0]
    assert toast.call_args.kwargs.get("kind") is FeedbackKind.WARNING
