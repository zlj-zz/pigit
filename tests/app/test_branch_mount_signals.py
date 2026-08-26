# -*- coding: utf-8 -*-
"""
Module: tests/app/test_branch_mount_signals.py
Description: BranchPanel rebinds vm.items on remount after TabView cold unmount.
Author: Zev
Date: 2026-08-25
"""

from __future__ import annotations

from unittest.mock import MagicMock

from pigit.app_branch import BranchPanel
from pigit.git.model import Branch
from pigit.termui.reactive import Signal


def _branch(name: str) -> Branch:
    return Branch(name=name, ahead="0", behind="0", is_head=False)


def test_branch_panel_rebinds_signal_after_unmount_remount():
    vm = MagicMock()
    vm.items = Signal([_branch("a")])
    vm.refresh = MagicMock()
    vm.dispose = MagicMock()
    panel = BranchPanel(vm=vm, id="branch")
    panel.mount()
    vm.items.set([_branch("a"), _branch("b"), _branch("c")])
    assert [b.name for b in panel.branches] == ["a", "b", "c"]

    panel.unmount()
    panel.mount()
    vm.items.set([_branch("x"), _branch("y")])
    assert [b.name for b in panel.branches] == ["x", "y"]
