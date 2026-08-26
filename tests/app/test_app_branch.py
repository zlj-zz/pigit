# -*- coding: utf-8 -*-
"""
Module: tests/app/test_app_branch.py
Description: Tests for BranchPanel row rendering, including upstream tracking.
Author: Zev
Date: 2026-08-18
"""

from __future__ import annotations

from unittest.mock import Mock

from pigit.app_branch import BranchPanel
from pigit.git.model import Branch
from pigit.termui.reactive import Signal
from pigit.viewmodels.branch import IBranchViewModel


def _panel_with(branches: list[Branch]) -> BranchPanel:
    vm = Mock(spec=IBranchViewModel)
    vm.items = Signal(branches)
    panel = BranchPanel(vm=vm)
    panel.branches = branches
    panel.content = [b.name for b in branches]
    return panel


def test_describe_row_shows_upstream_name():
    panel = _panel_with(
        [Branch("bug-fix", "0", "0", True, upstream_name="origin/bug-fix")]
    )
    _left, _main, right = panel.describe_row(0, is_cursor=False)
    text = "".join(seg.text for seg in right)
    assert "origin/bug-fix" in text


def test_describe_row_omits_upstream_when_unset():
    panel = _panel_with([Branch("bug-fix", "?", "?", True)])
    _left, _main, right = panel.describe_row(0, is_cursor=False)
    text = "".join(seg.text for seg in right)
    assert "origin/" not in text


def test_describe_row_colors_local_vs_remote():
    from pigit.app_theme import THEME
    from pigit.termui.theme import get_theme, set_theme

    prev = get_theme()
    set_theme(THEME)
    try:
        panel = _panel_with(
            [
                Branch("main", "0", "0", True),
                Branch("feature", "0", "0", False),
                Branch("origin/main", "?", "?", False, is_remote=True),
            ]
        )
        head_left, _, _ = panel.describe_row(0, is_cursor=False)
        local_left, _, _ = panel.describe_row(1, is_cursor=False)
        remote_left, _, _ = panel.describe_row(2, is_cursor=False)
        assert head_left[0].fg == THEME.fg_local_branch
        assert local_left[0].fg == THEME.fg_primary
        assert remote_left[0].fg == THEME.fg_remote_branch
    finally:
        set_theme(prev)
