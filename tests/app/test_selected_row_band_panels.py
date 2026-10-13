# -*- coding: utf-8 -*-
"""
Module: tests/app/test_selected_row_band_panels.py
Description: Status / Stash / Branch put the selection band on the cursor row.
Author: Zev
Date: 2026-10-13
"""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from pigit.app_branch import BranchPanel
from pigit.app_stash import StashPanel
from pigit.app_status import StatusPanel
from pigit.app_theme import THEME
from pigit.git.model import Branch, File, Stash
from pigit.termui.reactive import Signal
from pigit.termui.theme import get_theme, set_theme
from pigit.viewmodels.branch import IBranchViewModel
from pigit.viewmodels.status import IStatusViewModel


@pytest.fixture(autouse=True)
def _app_theme():
    """The app binds its own theme at startup (`app.py`, `set_theme(THEME)`).

    Without it `get_theme()` is the framework default, which carries no
    `bg_commit_selected` -- the band would fall back to `bg_hover` and these
    assertions would be testing the fallback instead of the band.
    """
    old = get_theme()
    set_theme(THEME)
    yield
    set_theme(old)


def _branch_panel(branches: list[Branch]) -> BranchPanel:
    vm = Mock(spec=IBranchViewModel)
    vm.items = Signal(branches)
    vm.load_error = Signal(None)
    panel = BranchPanel(
        vm=vm, get_git=lambda: Mock(bisect_status=Mock(return_value=None))
    )
    panel.branches = branches
    panel._recompute_meta_width()
    panel.content = [b.name for b in branches]
    return panel


def _stash_panel(stashes: list[Stash]) -> StashPanel:
    vm = Mock(spec=IStatusViewModel)
    vm.items = Signal([])
    vm.load_error = Signal(None)
    vm.load_stashes.return_value = stashes
    panel = StashPanel(vm=vm)
    panel.mount()
    panel.refresh()
    return panel


def _tree_status_panel() -> StatusPanel:
    """A Status panel in tree view with one directory row."""
    files = [
        File(
            name="docs/a.md",
            display_str="docs/a.md",
            short_status="??",
            has_staged_change=False,
            has_unstaged_change=True,
            tracked=False,
            deleted=False,
            added=False,
            has_merged_conflicts=False,
            has_inline_merged_conflicts=False,
        )
    ]
    vm = Mock(spec=IStatusViewModel)
    vm.items = Signal(files)
    vm.load_error = Signal(None)
    vm.repo_path = "/tmp/repo"
    panel = StatusPanel(vm=vm, default_view="tree")
    panel._all_files = list(files)
    panel._apply_filter()
    return panel


def _band(panel, idx: int, is_cursor: bool):
    left, _main, _right = panel.describe_row(idx, is_cursor=is_cursor)
    return left


def test_the_branch_cursor_row_wears_the_band():
    panel = _branch_panel(
        [Branch("dev", "0", "0", True), Branch("main", "0", "0", False)]
    )
    assert _band(panel, 0, True)[0].bg == THEME.bg_commit_selected


def test_branch_rows_below_the_cursor_do_not():
    panel = _branch_panel(
        [Branch("dev", "0", "0", True), Branch("main", "0", "0", False)]
    )
    assert all(seg.bg is None for seg in _band(panel, 1, False))


def test_the_stash_cursor_row_wears_the_band():
    panel = _stash_panel([Stash(ref="stash@{0}", sha="abc", msg="wip")])
    assert _band(panel, 0, True)[0].bg == THEME.bg_commit_selected
    assert all(seg.bg is None for seg in _band(panel, 0, False))


def test_the_status_cursor_row_wears_the_band():
    panel = _tree_status_panel()
    left, _main, _right = panel.describe_row(0, is_cursor=True)
    assert left[0].bg == THEME.bg_commit_selected
    assert all(seg.bg is None for seg in _band(panel, 0, False))


def test_a_row_past_the_end_is_not_banded_and_does_not_raise():
    """``describe_row`` answers an out-of-range index with no segments at all;
    there is nowhere to put the band, and it must not be indexed into."""
    panel = _branch_panel([Branch("dev", "0", "0", True)])
    left, _main, _right = panel.describe_row(99, is_cursor=True)
    assert left == []


def test_a_stolen_presentation_dims_the_band():
    """A sheet drives the keyboard, but the row is still the cursor row -- so
    the band stays and dims rather than vanishing.

    Headless panels always report themselves active, so without forcing it
    here the whole inactive path goes unexercised.
    """
    panel = _branch_panel([Branch("dev", "0", "0", True)])
    panel.is_presentation_active = lambda: False
    assert _band(panel, 0, True)[0].bg == THEME.bg_commit_selected_inactive


def test_a_stolen_presentation_leaves_the_summary_dim():
    """The lift exists because dim does not read on the band. With the band
    dimmed, dim reads again -- so the lift must not fire."""
    panel = _tree_status_panel()
    panel.is_presentation_active = lambda: False
    assert panel.describe_row(0, is_cursor=True)[2][0].fg == THEME.fg_dim


def test_the_status_summary_is_lifted_only_on_the_cursor_row():
    """Dim on the band is 1.8:1. Other rows keep the dim they always had —
    lifting them too would be a different change, to a different thing."""
    panel = _tree_status_panel()
    cursor_right = panel.describe_row(0, is_cursor=True)[2]
    plain_right = panel.describe_row(0, is_cursor=False)[2]
    assert cursor_right[0].fg == THEME.fg_muted
    assert plain_right[0].fg == THEME.fg_dim
