# -*- coding: utf-8 -*-
"""
Module: tests/app/test_worktree_gate_coverage.py
Description: Every working-tree-rewriting entry point defers to the session gate.
Author: Zev
Date: 2026-09-28
"""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

from pigit.app_merge_workflow import MergeWorkflow
from pigit.app_network_git import NetworkGit, NetworkGitOutcome
from pigit.app_rebase import RebasePanel
from pigit.app_sequencer import SequencerControl
from pigit.viewmodels.base import WORKTREE_BUSY_MESSAGE, WorktreeGate


def _idle_git() -> Mock:
    """A git stub whose sequencer/bisect guards both report 'nothing running'."""
    git = Mock()
    git.bisect_status.return_value = None
    git.sequencer_in_progress.return_value = None
    return git


def _merge_workflow(git: Mock, *, busy: bool) -> tuple[MergeWorkflow, Mock]:
    dialog = Mock()
    workflow = MergeWorkflow(
        store=Mock(),
        network=Mock(),
        get_git=lambda: git,
        navigate_product=Mock(),
        get_branch_panel=Mock(),
        get_alert_dialog=lambda: dialog,
        get_refresh_git_vms=Mock(),
        get_schedule_reload_header=Mock(),
        get_record_rewind=lambda: Mock(),
        get_worktree_busy=lambda: busy,
    )
    return workflow, dialog


def test_merge_request_refuses_while_a_rewrite_runs():
    """A merge is three subprocesses and a HEAD move; it must not start on a
    worktree that is still being rewritten."""
    workflow, dialog = _merge_workflow(_idle_git(), busy=True)

    with patch("pigit.app_bisect.show_toast") as toast:
        workflow.on_merge_request("feat", "main")

    assert toast.call_args[0][0] == WORKTREE_BUSY_MESSAGE
    dialog.assert_not_called()  # never even asked to confirm


def test_merge_request_proceeds_when_idle():
    workflow, dialog = _merge_workflow(_idle_git(), busy=False)

    workflow.on_merge_request("feat", "main")

    dialog.alert.assert_called_once()


def test_sequencer_controls_refuse_while_a_rewrite_runs():
    ctrl = SequencerControl(
        get_git=_idle_git,
        get_repo_path=lambda: "/repo",
        navigate_product=Mock(),
        get_alert_dialog=lambda: Mock(),
        get_refresh_git_vms=Mock(),
        get_refresh_active_panel=Mock(),
        get_record_rewind=lambda: Mock(),
        get_worktree_busy=lambda: True,
    )

    with (
        patch("pigit.app_bisect.show_toast") as toast,
        patch("pigit.app_sequencer.exec_external") as external,
    ):
        ctrl.do_rebase_control("continue")
        ctrl.do_cherry_pick_control("continue")

    external.assert_not_called()
    assert [c[0][0] for c in toast.call_args_list] == [
        WORKTREE_BUSY_MESSAGE,
        WORKTREE_BUSY_MESSAGE,
    ]


def test_rebase_execute_refuses_while_a_rewrite_runs():
    panel = RebasePanel(
        _idle_git(),
        "main",
        on_done=Mock(),
        get_record_rewind=lambda: Mock(),
        get_worktree_busy=lambda: True,
    )

    with (
        patch("pigit.app_bisect.show_toast") as toast,
        patch("pigit.app_rebase.exec_external") as external,
    ):
        panel._execute()

    external.assert_not_called()
    assert toast.call_args[0][0] == WORKTREE_BUSY_MESSAGE


def _network(gate: WorktreeGate) -> tuple[NetworkGit, list]:
    """NetworkGit with its worker captured instead of run."""
    calls: list = []
    task = Mock()
    task.start.side_effect = lambda work, done, **kw: calls.append((work, done))
    git = Mock()
    git.has_upstream.return_value = True
    network = NetworkGit(
        store=Mock(),
        get_git=lambda: git,
        navigate_product=Mock(),
        get_sync_task=lambda: task,
        get_refresh_git_vms=Mock(),
        get_schedule_reload_header=Mock(),
        get_alert_dialog=lambda: Mock(),
        get_worktree_gate=lambda: gate,
        guard_async=None,
    )
    return network, calls


def test_pull_takes_and_releases_the_gate():
    gate = WorktreeGate()
    network, calls = _network(gate)

    network.run("pull")
    assert gate.busy is True  # held for the duration of the worker

    calls[0][1](NetworkGitOutcome(ok=True))
    assert gate.busy is False


def test_pull_refuses_while_a_rewrite_runs():
    gate = WorktreeGate()
    assert gate.acquire() is True
    network, calls = _network(gate)

    with patch("pigit.app_network_git.show_toast") as toast:
        network.run("pull")

    assert calls == []  # no worker started
    assert toast.call_args[0][0] == WORKTREE_BUSY_MESSAGE
    assert gate.busy is True  # the other operation keeps its gate


def test_push_never_releases_a_gate_it_did_not_take():
    """Push does not rewrite the worktree, so it takes nothing — and an
    unconditional release in its completion callback would hand a concurrent
    checkout's gate to a third operation mid-rewrite."""
    gate = WorktreeGate()
    assert gate.acquire() is True  # a checkout is running
    network, calls = _network(gate)

    network.run("push")
    calls[0][1](NetworkGitOutcome(ok=True))

    assert gate.busy is True


def test_finish_merge_checkout_refuses_while_a_rewrite_runs():
    """Reached after the push worker finished, so the loop ran again in
    between: the gate can have been taken since the entry check."""
    git = _idle_git()
    workflow, _dialog = _merge_workflow(git, busy=True)

    with patch("pigit.app_bisect.show_toast") as toast:
        workflow.finish_merge_checkout("main", "feat")

    git.checkout_branch.assert_not_called()
    assert toast.call_args[0][0] == WORKTREE_BUSY_MESSAGE


def test_cherry_pick_entry_refuses_while_a_rewrite_runs():
    ctrl = SequencerControl(
        get_git=_idle_git,
        get_repo_path=lambda: "/repo",
        navigate_product=Mock(),
        get_alert_dialog=lambda: Mock(),
        get_refresh_git_vms=Mock(),
        get_refresh_active_panel=Mock(),
        get_record_rewind=lambda: Mock(),
        get_worktree_busy=lambda: True,
    )

    with (
        patch("pigit.app_bisect.show_toast") as toast,
        patch("pigit.app_sequencer.exec_external") as external,
    ):
        ctrl.on_cherry_pick("abcdef0", False)

    external.assert_not_called()
    assert toast.call_args[0][0] == WORKTREE_BUSY_MESSAGE
