# -*- coding: utf-8 -*-
"""
Module: tests/app/test_worktree_gate.py
Description: One shared gate serialises working-tree rewrites across panels.
Author: Zev
Date: 2026-09-25
"""

from __future__ import annotations

from unittest.mock import Mock

from pigit.git.model import Branch
from pigit.viewmodels.base import WORKTREE_BUSY_MESSAGE, WorktreeGate
from pigit.viewmodels.branch import BranchViewModel
from pigit.viewmodels.status import StatusViewModel


def _branch_vm(gate: WorktreeGate, git: Mock | None = None) -> BranchViewModel:
    git = git if git is not None else Mock()
    git.get_head.return_value = "main"
    vm = BranchViewModel(git, worktree_gate=gate)
    vm._items.set([Branch("feat", "0", "0", False)])
    return vm


def test_rewrites_across_panels_are_serialised():
    """The hole the per-panel flag could not close: a checkout started on
    Branch and a stash pop on Status rewrite the same working tree. The gate
    is held by a real op here, not grabbed by hand — sharing one instance is
    the whole point of the design."""
    gate = WorktreeGate()
    git = Mock()
    git.get_head.return_value = "main"
    branch_vm = _branch_vm(gate, git)
    status_vm = StatusViewModel(Mock(), worktree_gate=gate)
    refused: list[str] = []

    def _checkout(_name):
        # Sitting inside the Branch rewrite, Status tries to pop a stash.
        refused.append(status_vm.stash_apply("stash@{0}").message)
        refused.append(status_vm.stash_push("wip").message)

    git.checkout_branch.side_effect = _checkout

    assert branch_vm.checkout(0).success is True
    assert refused == [WORKTREE_BUSY_MESSAGE, WORKTREE_BUSY_MESSAGE]
    # ...and the gate is free again once the checkout returns.
    assert status_vm.stash_apply("stash@{0}").success is True


def test_gate_is_released_when_the_rewrite_raises():
    """A failed checkout must not wedge the gate for the rest of the session."""
    gate = WorktreeGate()
    git = Mock()
    git.get_head.return_value = "main"
    git.checkout_branch.side_effect = RuntimeError("worktree locked")
    vm = _branch_vm(gate, git)

    assert vm.checkout(0).success is False
    assert gate.busy is False
    assert gate.acquire() is True


def test_gate_is_released_after_success():
    gate = WorktreeGate()
    vm = _branch_vm(gate)

    assert vm.checkout(0).success is True
    assert gate.busy is False
