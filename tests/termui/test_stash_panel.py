# -*- coding: utf-8 -*-
"""
Module: tests/termui/test_stash_panel.py
Description: Tests for StashPanel section header and list rendering.
Author: Zev
Date: 2026-08-17
"""

from __future__ import annotations

from unittest.mock import Mock

from pigit.app_stash import StashPanel
from pigit.git.model import Stash
from pigit.termui import palette
from pigit.termui._surface import Surface
from pigit.termui.reactive import Signal
from pigit.viewmodels.status import IStatusViewModel


def _panel_with_stashes(msgs: list[str]) -> StashPanel:
    vm = Mock(spec=IStatusViewModel)
    vm.items = Signal([])
    vm.load_stashes.return_value = [
        Stash(ref=f"stash@{{{i}}}", sha=f"abc{i}", msg=msg)
        for i, msg in enumerate(msgs)
    ]
    panel = StashPanel(vm=vm)
    panel.activate()
    return panel


def test_section_header_right_label_with_tail():
    """Top row is fill dashes, bold Stash, then two trailing dashes."""
    panel = _panel_with_stashes(["WIP on main"])
    panel.resize((40, 6))
    surface = Surface(40, 6)
    panel._render_surface(surface)

    row = "".join(c.char for c in surface._rows[0]).rstrip("\x00").rstrip()
    assert row.endswith("Stash ──")
    assert "─" in row
    # Label cells are bold
    label_start = row.index("Stash")
    for col in range(label_start, label_start + 5):
        assert surface._rows[0][col].style_flags & palette.STYLE_BOLD


def test_visible_row_count_excludes_header():
    panel = _panel_with_stashes(["a", "b", "c"])
    panel.resize((40, 5))
    assert panel.visible_row_count == 4
