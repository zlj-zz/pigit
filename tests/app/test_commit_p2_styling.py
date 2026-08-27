"""
Module: tests/app/test_commit_p2_styling.py
Description: Commit panel and contribution graph styling regressions.
Author: Zev
Date: 2026-08-27
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import Mock

import datetime

from pigit.app_contribution_graph import ContributionGraph
from pigit.app_theme import THEME
from pigit.app_types import GraphRow
from pigit.git.model import Commit
from pigit.termui import palette
from pigit.termui.reactive import Signal
from pigit.viewmodels.commit import ICommitViewModel

from tests.app.test_presentation_inactive_panels import _steal_presentation

if TYPE_CHECKING:
    from pigit.app_commit import CommitPanel


def _head_commit(extra_info: str = " (HEAD -> dev)") -> Commit:
    return Commit(
        "abc1234ffff",
        "fix bug",
        "Zev",
        0,
        "pushed",
        extra_info,
        [],
    )


def _commit_panel(*, graph_rows: list | None = None) -> "CommitPanel":
    from pigit.app_commit import CommitPanel

    vm = Mock(spec=ICommitViewModel)
    vm.items = Signal([])
    vm.graph_rows = graph_rows or []
    vm.remotes = ()
    return CommitPanel(vm=vm)


def test_is_head_commit_via_extra_info() -> None:
    panel = _commit_panel()
    assert panel._is_head_commit(_head_commit()) is True
    panel._refs_cache.clear()
    assert panel._is_head_commit(_head_commit(" (HEAD)")) is True
    panel._refs_cache.clear()
    no_head = Commit(
        "bbbbbbbffff",
        "plain",
        "Zev",
        0,
        "pushed",
        "",
        [],
    )
    assert panel._is_head_commit(no_head) is False


def test_ref_segments_orange_parens_and_semantic_fg() -> None:
    panel = _commit_panel()
    commit = _head_commit()
    panel.commits = [commit]
    panel.content = [commit.msg]
    _left, main, _right = panel.describe_row(0, is_cursor=False)
    text = "".join(s.text for s in main)
    assert "(HEAD -> dev)" in text.replace(" ", "") or "HEAD" in text and "dev" in text
    ref_fgs = {s.fg for s in main if s.text in ("HEAD", "dev", " -> ")}
    assert THEME.fg_info in ref_fgs
    assert THEME.fg_local_branch in ref_fgs
    assert all(s.bg is None for s in main if s.text != commit.msg)


def test_head_row_has_no_background_when_not_cursor() -> None:
    panel = _commit_panel()
    commit = _head_commit()
    panel.commits = [commit]
    panel.content = [commit.msg]
    left, main, right = panel.describe_row(0, is_cursor=False)
    assert all(s.bg is None for s in left)
    assert all(s.bg is None for s in main)
    assert right[0].bg is None


def test_selected_row_full_background() -> None:
    panel = _commit_panel()
    commit = _head_commit()
    panel.commits = [commit]
    panel.content = [commit.msg]
    left, main, right = panel.describe_row(0, is_cursor=True)
    assert all(s.bg == THEME.bg_commit_selected for s in left)
    assert all(s.bg == THEME.bg_commit_selected for s in main)
    assert right[0].bg == THEME.bg_commit_selected
    painted = panel._with_cursor_mark(left, is_cursor=True)
    assert painted[0].bg == THEME.bg_commit_selected


def test_detached_head_ref_text() -> None:
    panel = _commit_panel()
    commit = _head_commit(" (HEAD)")
    panel.commits = [commit]
    panel.content = [commit.msg]
    _left, main, _right = panel.describe_row(0, is_cursor=False)
    assert any(s.text == "HEAD" for s in main)
    assert not any("->" in s.text for s in main)


def test_head_commit_glyph_uses_fg_head_commit() -> None:
    commit = _head_commit()
    graph_rows = [
        GraphRow(
            lanes_before=[],
            commit_lane=0,
            closed_lanes=[],
            opened_lanes=[],
            lanes_after=[commit.sha],
        )
    ]
    panel = _commit_panel(graph_rows=graph_rows)
    panel.commits = [commit]
    panel.content = [commit.msg]
    left, _main, _right = panel.describe_row(0, is_cursor=False)
    glyph = [s for s in left if s.text.startswith(panel.GRAPH_COMMIT)][0]
    assert glyph.fg == THEME.fg_head_commit


def test_unpushed_head_uses_yellow_over_head_blue() -> None:
    commit = Commit(
        "deadbeefaaaa",
        "wip",
        "Zev",
        0,
        "unpushed",
        " (HEAD -> dev)",
        [],
    )
    graph_rows = [
        GraphRow(
            lanes_before=[],
            commit_lane=0,
            closed_lanes=[],
            opened_lanes=[],
            lanes_after=[commit.sha],
        )
    ]
    panel = _commit_panel(graph_rows=graph_rows)
    panel.commits = [commit]
    panel.content = [commit.msg]
    left, _main, _right = panel.describe_row(0, is_cursor=False)
    glyph = [s for s in left if s.text.startswith(panel.GRAPH_COMMIT)][0]
    assert glyph.fg == THEME.fg_unpushed_commit
    assert glyph.fg != THEME.fg_head_commit


def test_head_glyph_stays_semantic_under_steal() -> None:
    commit = _head_commit()
    graph_rows = [
        GraphRow(
            lanes_before=[],
            commit_lane=0,
            closed_lanes=[],
            opened_lanes=[],
            lanes_after=[commit.sha],
        )
    ]
    panel = _commit_panel(graph_rows=graph_rows)
    panel.commits = [commit]
    panel.content = [commit.msg]
    _steal_presentation()
    left, _main, _right = panel.describe_row(0, is_cursor=False)
    glyph = [s for s in left if s.text.startswith(panel.GRAPH_COMMIT)][0]
    assert glyph.fg == THEME.fg_head_commit


def test_chart_author_colors_distinct_hues() -> None:
    colors = THEME.chart_author_colors
    assert len(colors) == 6
    assert len(set(colors)) == 6
    for color, hue in zip(
        colors,
        (
            palette.ACCENT,
            palette.GREEN,
            palette.AMBER,
            palette.MAGENTA,
            palette.CYAN,
            palette.PURPLE,
        ),
    ):
        assert color != hue
        assert color != palette.STEEL


def test_author_chart_color_stable_by_name() -> None:
    from pigit.app_contribution_graph import _author_chart_color

    a = _author_chart_color("chengjian")
    b = _author_chart_color("chengjian")
    c = _author_chart_color("zhanglijun")
    assert a == b
    assert a in THEME.chart_author_colors
    assert c in THEME.chart_author_colors


def test_current_week_highlight_column() -> None:
    graph = ContributionGraph()
    first_monday = datetime.date(2026, 8, 25)
    today = datetime.date(2026, 9, 1)
    num_weeks = 4
    content_h = 12
    from pigit.termui.surface import Surface

    canvas = Surface(20, content_h)
    heat_fg = THEME.contrib_heatmap_colors[3]
    for day in range(3):
        canvas.draw_text_rgb(1 + day, 4, "■", fg=heat_fg, bg=None)
    window = {(1, day): 2 for day in range(3)}
    graph._max_count = 2
    graph._draw_current_week_frame(
        canvas,
        today=today,
        first_monday=first_monday,
        num_weeks=num_weeks,
        content_h=content_h,
        window=window,
    )
    rows = canvas.rows()
    today_week = (today - first_monday).days // 7
    assert today_week == 1
    assert rows[1][4].char == "■"
    assert rows[1][4].fg == heat_fg
    assert rows[1][5].char == "■"
    assert rows[1][5].fg != heat_fg
    assert not any(cell.char == "─" for row in rows for cell in row)


def test_current_week_highlight_skips_out_of_range() -> None:
    from pigit.termui.surface import Surface

    graph = ContributionGraph()
    canvas = Surface(20, 12)
    today = datetime.date(2026, 8, 27)
    first_monday = datetime.date(2026, 7, 28)
    graph._draw_current_week_frame(
        canvas,
        today=today,
        first_monday=first_monday,
        num_weeks=4,
        content_h=12,
        window={},
    )
    assert not any(
        cell.fg == THEME.fg_contrib_week_frame for row in canvas.rows() for cell in row
    )
