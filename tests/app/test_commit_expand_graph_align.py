# -*- coding: utf-8 -*-
"""
Module: tests/app/test_commit_expand_graph_align.py
Description: Expanded commit rows keep graph rails column-aligned with COMMIT.
Author: Zev
Date: 2026-08-26
"""

from __future__ import annotations

from unittest.mock import Mock

from pigit.app_commit import CommitPanel
from pigit.app_types import GraphRow
from pigit.git.model import Commit
from pigit.termui.reactive import Signal
from pigit.termui.wcwidth_table import wcswidth
from pigit.viewmodels.commit import ICommitViewModel


def _graph_glyph_col(panel: CommitPanel, left) -> int:
    """Display column of the first graph glyph after cursor-mark painting."""
    painted = panel._with_cursor_mark(left, is_cursor=False)
    col = 0
    for seg in painted:
        if panel.GRAPH_COMMIT in seg.text or panel.GRAPH_VERTICAL in seg.text:
            return col
        col += wcswidth(seg.text)
    raise AssertionError("no graph glyph in left segments")


def test_expanded_sub_rows_align_rails_with_commit_row():
    """Sub-rows must use the same one-column GRAPH_PAD as COMMIT rows so
    ``│`` stacks under ``◉`` after OptionList prepends the cursor mark.
    """
    commit = Commit(
        "deadbeefaaaa",
        "merge commit",
        "A",
        0,
        "pushed",
        "",
        [],
        parents=["aaa", "bbb"],
    )
    vm = Mock(spec=ICommitViewModel)
    vm.items = Signal([])
    vm.remotes = ()
    vm.graph_rows = [
        GraphRow(
            lanes_before=[],
            commit_lane=0,
            closed_lanes=[],
            opened_lanes=[],
            lanes_after=["deadbeefaaaa"],
        )
    ]
    panel = CommitPanel(vm=vm)
    panel.commits = [commit]
    panel._expanded = True
    lines, starts = panel._build_expanded()
    panel.set_content(lines)
    panel.set_item_starts(starts)

    commit_row = starts[0]
    author_row = commit_row + 2  # COMMIT, MERGE, AUTHOR
    left_c, _, _ = panel.describe_row(commit_row, is_cursor=True, item_idx=0, sub_row=0)
    left_a, _, _ = panel.describe_row(
        author_row, is_cursor=False, item_idx=0, sub_row=2
    )
    assert left_c[0].text == CommitPanel.GRAPH_PAD
    assert left_a[0].text == CommitPanel.GRAPH_PAD
    assert _graph_glyph_col(panel, left_c) == _graph_glyph_col(panel, left_a)
