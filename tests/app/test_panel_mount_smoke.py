# -*- coding: utf-8 -*-
"""
Module: tests/app/test_panel_mount_smoke.py
Description: Smoke tests for panel mount/unmount/focus lifecycle contracts.
Author: Zev
Date: 2026-08-26
"""

from __future__ import annotations

from unittest.mock import MagicMock, Mock

from pigit.app_branch import BranchPanel
from pigit.app_recent_actions import RecentActionsPanel
from pigit.app_stash import StashPanel
from pigit.git.model import Branch, Stash
from pigit.termui.containers import Column
from pigit.termui.reactive import Signal


def _branch(name: str) -> Branch:
    return Branch(name=name, ahead="0", behind="0", is_head=False)


def test_branch_panel_rebinds_signal_after_unmount_remount():
    vm = MagicMock()
    vm.items = Signal([_branch("a")])
    vm.refresh = MagicMock()
    panel = BranchPanel(get_git=lambda: Mock(bisect_status=Mock(return_value=None)), vm=vm, id="branch")
    panel.mount()
    vm.items.set([_branch("a"), _branch("b"), _branch("c")])
    assert [b.name for b in panel.branches] == ["a", "b", "c"]

    panel.unmount()
    panel.mount()
    vm.items.set([_branch("x"), _branch("y")])
    assert [b.name for b in panel.branches] == ["x", "y"]


def test_stash_set_vm_reloads_when_mounted():
    old_vm = MagicMock()
    old_vm.load_stashes = MagicMock(return_value=[])
    new_vm = MagicMock()
    new_vm.load_stashes = MagicMock(
        return_value=[Stash(ref="stash@{0}", sha="abc", msg="wip")]
    )
    panel = StashPanel(vm=old_vm, id="stash")
    panel.mount()
    panel.set_vm(new_vm)
    assert new_vm.load_stashes.call_count == 1
    assert len(panel.stashes) == 1
    assert panel._vm is new_vm


def test_mount_sets_is_mounted():
    history = MagicMock()
    history.peek.return_value = []
    panel = RecentActionsPanel(
        history=history,
        git=MagicMock(),
        on_done=lambda: None,
    )
    assert not panel.is_mounted()
    panel.mount()
    assert panel.is_mounted()
    history.peek.assert_called()


def test_stash_does_not_load_on_column_mount_until_focused():
    vm = MagicMock()
    vm.load_stashes = MagicMock(
        return_value=[Stash(ref="stash@{0}", sha="abc", msg="wip")]
    )
    status = MagicMock()
    status.mount = MagicMock()
    status.on_focus = MagicMock()
    stash = StashPanel(vm=vm, id="stash")
    col = Column(children=[status, stash], heights=["flex", "flex"], focus_index=0)
    col.mount()
    assert vm.load_stashes.call_count == 0
    assert stash.stashes == []

    col.set_focus_index(1)
    assert vm.load_stashes.call_count == 1
    assert len(stash.stashes) == 1
