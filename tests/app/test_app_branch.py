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
    vm.load_error = Signal(None)
    panel = BranchPanel(
        get_git=lambda: Mock(bisect_status=Mock(return_value=None)), vm=vm
    )
    panel.branches = branches
    panel._recompute_meta_width()  # the app does this in _on_items_changed
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


# ── The current branch is marked in text, not only in colour ──
#
# HEAD and a plain local branch rendered identical text; only the foreground
# colour told them apart, which leaves colour-blind users, NO_COLOR users and
# low-contrast terminals unable to see which branch they are on.


def _row_text(panel: BranchPanel, idx: int) -> str:
    left, main, right = panel.describe_row(idx, is_cursor=False)
    return "".join(seg.text for seg in left + (main or []) + right)


def _prefix(panel: BranchPanel, idx: int) -> tuple[str, str]:
    """The status lane's mark and the name, which are separate lanes now."""
    left, main, _right = panel.describe_row(idx, is_cursor=False)
    return left[0].text, main[0].text


def test_the_current_branch_carries_a_marker():
    panel = _panel_with([Branch("dev", "0", "0", True)])
    mark, name = _prefix(panel, 0)
    assert mark == "*"
    assert name == "dev"


def test_other_branches_have_no_marker():
    panel = _panel_with(
        [Branch("dev", "0", "0", True), Branch("feature", "0", "0", False)]
    )
    mark, name = _prefix(panel, 1)
    assert mark != "*"
    assert name == "feature"


def test_the_marker_does_not_shift_the_name_column():
    panel = _panel_with(
        [Branch("dev", "0", "0", True), Branch("feature", "0", "0", False)]
    )
    marked = _row_text(panel, 0)
    plain = _row_text(panel, 1)
    assert marked.index("dev") == plain.index("feature")


def test_the_same_branch_reads_differently_as_head_and_as_not():
    """The point of the marker, stated so it can fail: hold everything but
    ``is_head`` constant. Comparing rows that already differ by name would
    prove nothing — those differ with or without a marker.

    ``_row_text`` concatenates ``.text`` only, so this is the row as it reads
    with every colour discarded.
    """
    as_head = _panel_with([Branch("dev", "0", "0", True)])
    as_plain = _panel_with([Branch("dev", "0", "0", False)])

    assert _row_text(as_head, 0) != _row_text(as_plain, 0)


# ── Tip dates ──


def test_the_branch_row_shows_its_tip_date():
    import time

    panel = _panel_with([Branch("dev", "0", "0", True, committed_at=int(time.time()))])
    assert "0s ago" in _row_text(panel, 0)


def test_a_remote_branch_shows_its_date_too():
    """Remote rows have no upstream line, but they are sorted by this same
    date — so they need it shown at least as much as local ones do."""
    import time

    panel = _panel_with(
        [
            Branch(
                "origin/main",
                "0",
                "0",
                False,
                is_remote=True,
                committed_at=int(time.time()),
            )
        ]
    )
    assert "0s ago" in _row_text(panel, 0)


def test_an_unknown_date_renders_nothing():
    """relative_time(0) is not "a long time ago" — it computes weeks since
    the epoch, which would render as a huge bogus age."""
    panel = _panel_with([Branch("dev", "0", "0", True, committed_at=0)])
    text = _row_text(panel, 0)
    assert "ago" not in text


def test_the_marker_and_the_date_coexist():
    import time

    panel = _panel_with([Branch("dev", "0", "0", True, committed_at=int(time.time()))])
    mark, name = _prefix(panel, 0)
    assert (mark, name) == ("*", "dev")
    assert "ago" in _row_text(panel, 0)
