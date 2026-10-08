# -*- coding: utf-8 -*-
"""
Module: tests/app/test_rebase_control.py
Description: Tests for app-level rebase --continue/--abort/--skip control.
Author: Zev
Date: 2026-08-17
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from pigit.app import PigitApplication
from pigit.config_data import AppConfig
from pigit.termui import FeedbackKind


@pytest.fixture
def app():
    """Create a PigitApplication with mocked git/VMs for rebase control."""
    app = PigitApplication(config=AppConfig())
    app._git = MagicMock()
    app._branch_vm = MagicMock()
    app._commit_vm = MagicMock()
    app._status_vm = MagicMock()
    return app


def _run(app, flag: str, returncode: int = 0, in_progress: bool = False) -> tuple:
    """Run SequencerControl.do_rebase_control and return the captured toast."""
    app._git.is_rebase_in_progress.return_value = in_progress
    app._git.sequencer_in_progress.return_value = "rebase" if in_progress else None
    with (
        patch("pigit.app_sequencer.exec_external") as ex,
        patch("pigit.app_sequencer.show_toast") as toast,
    ):
        ex.return_value.returncode = returncode
        app._sequencer.do_rebase_control(flag)
    return toast.call_args


class TestRebaseControl:
    def test_continue_reports_completed_when_finished(self, app):
        """A --continue that ends the rebase reports success."""
        args, kwargs = _run(app, "continue", returncode=0, in_progress=False)
        assert "completed" in args[0]
        assert kwargs["kind"] is FeedbackKind.SUCCESS
        app._branch_vm.refresh.assert_called_once()

    def test_continue_reports_paused_when_rebase_still_active(self, app):
        """A --continue that resumes into another pause reports 'paused', not 'completed'."""
        args, kwargs = _run(app, "continue", returncode=0, in_progress=True)
        assert "paused" in args[0].lower()
        assert kwargs["kind"] is FeedbackKind.WARNING
        app._branch_vm.refresh.assert_called_once()

    def test_skip_reports_paused_when_rebase_still_active(self, app):
        """--skip into another edit/pause reports 'paused', not 'completed'."""
        args, kwargs = _run(app, "skip", returncode=0, in_progress=True)
        assert "paused" in args[0].lower()
        assert kwargs["kind"] is FeedbackKind.WARNING

    def test_control_reports_failure(self, app):
        """A non-zero returncode reports failure."""
        args, kwargs = _run(app, "continue", returncode=1, in_progress=False)
        assert "failed" in args[0]
        assert kwargs["kind"] is FeedbackKind.ERROR

    def test_continue_argv_is_git_rebase(self, app):
        app._git.sequencer_in_progress.return_value = None
        app._git.is_rebase_in_progress.return_value = False
        with (
            patch("pigit.app_sequencer.exec_external") as ex,
            patch("pigit.app_sequencer.show_toast"),
        ):
            ex.return_value.returncode = 0
            app._sequencer.do_rebase_control("continue")
        assert ex.call_args.args[0] == ["git", "rebase", "--continue"]


def test_the_controls_are_declared_as_actions():
    """They are reached by name, so they have to be bindings -- that is what
    puts them in the palette and in Help."""
    from pigit.app_keybindings import collect_all_action_bindings

    declared = {binding.action for _, binding in collect_all_action_bindings()}
    for name in (
        "universal.rebase_continue",
        "universal.rebase_abort",
        "universal.rebase_skip",
        "universal.cherry_pick_continue",
        "universal.cherry_pick_abort",
        "universal.cherry_pick_skip",
        "universal.continue_merge",
        "universal.fetch",
    ):
        assert name in declared


class TestTheControlRefusesOutsideItsSequencer:
    """The palette offers every control at any time, so the refusal has to be
    in the handler -- otherwise ``git rebase --continue`` runs outside a rebase
    and the user gets git's error instead of ours."""

    def test_rebase_control_refuses_when_no_rebase_is_running(self, app):
        app._git.sequencer_in_progress.return_value = None
        app._sequencer._get_git = lambda: app._git
        with (
            patch("pigit.app_sequencer.exec_external") as ex,
            patch("pigit.app_sequencer.show_toast") as toast,
        ):
            app._sequencer.run_rebase_control("continue")
        ex.assert_not_called()
        assert "No rebase in progress" in toast.call_args[0][0]
        assert toast.call_args[1]["kind"] is FeedbackKind.WARNING

    def test_rebase_control_runs_during_a_rebase(self, app):
        app._git.sequencer_in_progress.return_value = "rebase"
        app._sequencer._get_git = lambda: app._git
        with (
            patch("pigit.app_sequencer.exec_external") as ex,
            patch("pigit.app_sequencer.show_toast"),
        ):
            ex.return_value.returncode = 0
            app._sequencer.run_rebase_control("continue")
        assert ex.call_args.args[0] == ["git", "rebase", "--continue"]

    def test_cherry_pick_control_refuses_when_no_cherry_pick_is_running(self, app):
        app._git.sequencer_in_progress.return_value = "rebase"
        app._sequencer._get_git = lambda: app._git
        with (
            patch("pigit.app_sequencer.exec_external") as ex,
            patch("pigit.app_sequencer.show_toast") as toast,
        ):
            app._sequencer.run_cherry_pick_control("continue")
        ex.assert_not_called()
        assert "No cherry-pick in progress" in toast.call_args[0][0]

    def test_cherry_pick_control_resumes_a_paused_revert(self, app):
        """A paused revert is resumed through the cherry-pick controls --
        ``_SEQUENCER_PAUSED`` sends the user here -- so "revert" must be
        allowed, not refused."""
        app._git.sequencer_in_progress.return_value = "revert"
        app._sequencer._get_git = lambda: app._git
        with (
            patch("pigit.app_sequencer.exec_external") as ex,
            patch("pigit.app_sequencer.show_toast"),
        ):
            ex.return_value.returncode = 0
            app._sequencer.run_cherry_pick_control("continue")
        assert ex.call_args.args[0] == [
            "git",
            "cherry-pick",
            "--continue",
            "--no-edit",
        ]


class TestCherryPickControl:
    def test_continue_uses_no_edit(self, app):
        app._git.sequencer_in_progress.return_value = None
        with (
            patch("pigit.app_sequencer.exec_external") as ex,
            patch("pigit.app_sequencer.show_toast"),
        ):
            ex.return_value.returncode = 0
            app._sequencer.do_cherry_pick_control("continue")
        assert ex.call_args.args[0] == [
            "git",
            "cherry-pick",
            "--continue",
            "--no-edit",
        ]

    def test_skip_argv(self, app):
        app._git.sequencer_in_progress.return_value = None
        with (
            patch("pigit.app_sequencer.exec_external") as ex,
            patch("pigit.app_sequencer.show_toast"),
        ):
            ex.return_value.returncode = 0
            app._sequencer.do_cherry_pick_control("skip")
        assert ex.call_args.args[0] == ["git", "cherry-pick", "--skip"]

    def test_abort_argv(self, app):
        app._git.sequencer_in_progress.return_value = None
        with (
            patch("pigit.app_sequencer.exec_external") as ex,
            patch("pigit.app_sequencer.show_toast"),
        ):
            ex.return_value.returncode = 0
            app._sequencer.do_cherry_pick_control("abort")
        assert ex.call_args.args[0] == ["git", "cherry-pick", "--abort"]
