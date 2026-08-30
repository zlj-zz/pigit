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


def test_palette_lists_cherry_pick_controls():
    from pigit.app_command_palette import KNOWN_COMMAND_IDS

    for name in (
        "cherry-pick-continue",
        "cherry-pick-abort",
        "cherry-pick-skip",
    ):
        assert name in KNOWN_COMMAND_IDS


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
