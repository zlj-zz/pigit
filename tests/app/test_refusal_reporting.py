# -*- coding: utf-8 -*-
"""
Module: tests/app/test_refusal_reporting.py
Description: A refused action is reported without evicting the running spinner.
Author: Zev
Date: 2026-10-09
"""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

from pigit.app_theme import report_refusal
from pigit.git.model import Branch
from pigit.termui import Component
from pigit.termui._layer import LayerKind
from pigit.termui._runtime_context import RuntimeContext, _runtime_ctx
from pigit.termui.overlay import show_spinner
from pigit.termui.root import ComponentRoot
from pigit.viewmodels.base import WORKTREE_BUSY_MESSAGE, ActionResult, WorktreeGate, run_gated


def _refused() -> ActionResult:
    """A result of the kind a blocked gate produces: nothing ran."""
    return run_gated(_blocked_gate(), lambda: ActionResult(success=True))


def _blocked_gate() -> WorktreeGate:
    gate = WorktreeGate()
    gate.acquire()
    return gate


class _Body(Component):
    """The overlay host needs something to paint."""

    def paint(self, surface) -> None:
        pass


@pytest.fixture
def runtime():
    ctx = RuntimeContext()
    token = _runtime_ctx.set(ctx)
    root = ComponentRoot(_Body())
    ctx.overlay_host = root
    ctx.focus_manager = root._focus_manager
    yield root
    _runtime_ctx.reset(token)


def _top_message(root: ComponentRoot) -> str | None:
    toast = root._layer_stack.top(LayerKind.TOAST)
    return getattr(toast, "message", None) if toast is not None else None


class TestTheOutcome:
    def test_a_gate_refusal_is_its_own_outcome(self):
        """Not a failure: nothing was attempted. The distinction is what lets
        the renderers pick a different channel for it."""
        refused = run_gated(_blocked_gate(), lambda: ActionResult(success=True))
        assert refused.refused is True
        assert refused.success is False
        assert refused.message == WORKTREE_BUSY_MESSAGE

    def test_a_real_action_is_not_marked_refused(self):
        ran = run_gated(WorktreeGate(), lambda: ActionResult(success=True))
        assert ran.success is True
        assert ran.refused is False


class TestTheChannel:
    def test_a_refusal_goes_to_the_badge(self, runtime):
        with patch("pigit.app_theme.show_badge") as badge:
            assert report_refusal(_refused()) is True
        assert badge.call_args[0][0] == WORKTREE_BUSY_MESSAGE

    def test_a_refusal_is_not_reported_again_by_the_caller(self):
        assert report_refusal(ActionResult(success=True)) is False

    def test_a_refusal_leaves_the_running_spinner_alone(self, runtime):
        """The point of the whole change: the toast slot holds the operation
        that caused the refusal, and a refusal reported there evicts it."""
        show_spinner("Merging main into feat")
        assert "Merging" in _top_message(runtime)

        report_refusal(_refused())

        assert "Merging" in _top_message(runtime)
        assert WORKTREE_BUSY_MESSAGE not in _top_message(runtime)


class TestEveryRendererUsesIt:
    """Each of these used to send a refusal to the toast. They share the
    branch through :func:`report_refusal`, so they cannot drift apart."""

    def test_the_status_panel(self):
        from pigit.app_status import StatusPanel

        vm = Mock()
        vm.items = Mock()
        panel = StatusPanel(vm=vm, default_view="flat")
        with patch("pigit.app_status.report_refusal", return_value=True) as guard:
            panel._handle_result(_refused())
        guard.assert_called_once()

    def test_the_branch_panel(self):
        from pigit.app_branch import BranchPanel

        vm = Mock(spec=object)
        vm.items = Mock()
        panel = BranchPanel(vm=vm, get_git=lambda: Mock())
        with patch("pigit.app_branch.report_refusal", return_value=True) as guard:
            panel._handle_result(_refused())
        guard.assert_called_once()

    def test_the_stash_panel(self):
        from pigit.app_stash import StashPanel

        panel = StashPanel(vm=Mock(), id="stash")
        with patch("pigit.app_stash.report_refusal", return_value=True) as guard:
            panel._handle_result(_refused())
        guard.assert_called_once()

    def test_the_command_palette(self):
        from pigit.app import PigitApplication
        from pigit.config_data import AppConfig

        app = PigitApplication(config=AppConfig())
        with patch("pigit.app.report_refusal", return_value=True) as guard:
            app._toast_palette_result(_refused())
        guard.assert_called_once()

    @staticmethod
    def _status_panel():
        from pigit.app_status import StatusPanel

        vm = Mock()
        vm.items = Mock()
        vm.staged_files = [object()]
        return StatusPanel(vm=vm, default_view="flat")

    def test_commit_reports_a_refusal_on_the_badge(self):
        """commit renders its own result instead of going through
        ``_run_file_action``, so it needs the branch of its own."""
        panel = self._status_panel()
        with (
            patch("pigit.app_commit_editor.CommitEditor") as editor,
            patch("pigit.app_status.show_sheet"),
            patch("pigit.app_status.run_with_spinner") as spinner,
        ):
            panel.commit()
            editor.call_args.kwargs["on_submit"]("subject")
            done = spinner.call_args.args[1]

        with patch("pigit.app_status.report_refusal", return_value=True) as guard:
            done(_refused())

        guard.assert_called_once()

    def test_amend_reports_a_refusal_on_the_badge(self):
        panel = self._status_panel()
        with (
            patch("pigit.app_status.run_with_spinner") as spinner,
            patch.object(panel, "_confirm") as confirm,
        ):
            panel.amend()
            confirm.call_args.args[1](True)
            done = spinner.call_args.args[1]

        with patch("pigit.app_status.report_refusal", return_value=True) as guard:
            done(_refused())

        guard.assert_called_once()


class TestTheNonActionResultRefusals:
    def test_the_busy_guard_uses_the_badge(self):
        from pigit import app_bisect

        with patch("pigit.app_bisect.show_badge") as badge, patch(
            "pigit.app_bisect.show_toast"
        ) as toast:
            assert app_bisect.guard_worktree_busy(True) is True
        assert badge.call_args[0][0] == WORKTREE_BUSY_MESSAGE
        assert not toast.called
