# -*- coding: utf-8 -*-
"""
Module: tests/app/test_stash_focus_load.py
Description: StashPanel loads on Column focus, not on warm mount.
Author: Zev
Date: 2026-08-25
"""

from __future__ import annotations

from unittest.mock import MagicMock

from pigit.app_stash import StashPanel
from pigit.git.model import Stash
from pigit.termui.containers import Column


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
