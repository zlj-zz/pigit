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


def test_expanded_long_message_reads_row_by_row():
    """z 展开长 message：j 逐行下滚读完 body（视口跟随），跨入下一个 commit；
    body 内移动不改变选中 commit（curr_no 语义不变）。
    """
    body_lines = [f"body line {i}" for i in range(12)]
    commit_a = Commit("a" * 12, "subject a", "A", 0, "", "", [])
    commit_b = Commit("b" * 12, "subject b", "B", 0, "", "", [])
    vm = Mock(spec=ICommitViewModel)
    vm.items = Signal([])
    vm.remotes = ()
    vm.graph_rows = []
    vm.get_bodies.return_value = {commit_a.sha: "subject a\n\n" + "\n".join(body_lines)}
    panel = CommitPanel(vm=vm)
    panel.commits = [commit_a, commit_b]
    panel._expanded = True
    panel.resize(
        (80, 6)
    )  # viewport first: resize on an unmounted lazy panel wipes content
    panel._ensure_bodies()
    panel._rebuild_rows()

    # commit_a spans COMMIT+AUTHOR+DATE+BLANK+12 body lines+TAIL = 17 rows.
    assert panel._item_starts == [0, 17]

    panel.curr_no = 0
    panel._cursor_sub = 0
    panel._scroll_into_view()

    # j walks row by row through AUTHOR/DATE/BLANK/12 body lines/TAIL while
    # the selected commit stays put.
    for step in range(16):
        panel.next()
        assert panel.curr_no == 0
        assert panel.cursor_row() == 1 + step

    # One more step enters the next commit at its first sub-row.
    panel.next()
    assert (panel.curr_no, panel._cursor_sub) == (1, 0)

    # The viewport followed so the tail of the message was actually reachable.
    assert panel._r_start == 17 - 6 + 1
