"""
Module: tests/termui/test_calendar_layout.py
Description: Tests for contribution heatmap week-grid layout helpers.
Author: Zev
Date: 2026-08-20
"""

from __future__ import annotations

import datetime
from types import SimpleNamespace

from pigit.termui.primitives import (
    build_contribution_calendar,
    calendar_day_values,
)
from pigit.termui.surface import Surface
from pigit.termui.widgets.graph import StepLineChart
from pigit.app_contribution_graph import (
    ContributionGraph,
    _CELL_CHAR_W,
    _HEATMAP_ROWS,
    _LEFT_MARGIN,
    _TOP_MARGIN,
    _TOP_PAD,
)


def test_contribution_graph_excludes_future_cells():
    """Days after today in the final partial week render as blank, not '·'."""
    graph = ContributionGraph(size=(100, 24))
    graph.set_commits([])
    first_monday = graph._first_monday
    today = datetime.date.today()
    graph.paint(Surface(100, 24))
    for week, day in graph._heatmap._values:
        date = first_monday + datetime.timedelta(weeks=week, days=day)
        assert date <= today


def _day(days_ago: int, author: str = "Zev") -> SimpleNamespace:
    """Minimal commit stand-in: the graph reads only these two attributes."""
    stamp = datetime.datetime.now() - datetime.timedelta(days=days_ago, hours=1)
    return SimpleNamespace(unix_timestamp=int(stamp.timestamp()), author=author)


def _grid_column(surface: Surface, col: int) -> list[tuple[str, object]]:
    """Characters and fg colours down one heatmap column."""
    rows = range(_TOP_PAD + _TOP_MARGIN, _TOP_PAD + _TOP_MARGIN + _HEATMAP_ROWS)
    return [(surface._rows[r][col].char, surface._rows[r][col].fg) for r in rows]


def test_current_week_is_marked_by_tint_not_a_frame():
    """The marker is the cell tint; the one-sided ``│`` box is gone.

    Week columns are one wide with no gutter, so the box could never be drawn
    on both sides. The right bar was drawn every time — today is always in the
    last week — and the left never, so all you saw was a stray vertical line
    past the last column.
    """
    height = 30
    graph = ContributionGraph(size=(100, height))
    graph.set_commits([_day(0)])
    surface = Surface(100, height)
    graph.paint(surface)

    rows = ["".join(cell.char for cell in row) for row in surface._rows]
    assert not any("│" in row for row in rows)

    today_week = (datetime.date.today() - graph._first_monday).days // 7
    col = _LEFT_MARGIN + today_week * _CELL_CHAR_W
    assert _grid_column(surface, col) != _grid_column(surface, col - 1)


def test_heatmap_legend_shares_the_chart_legend_row():
    """Both legends sit on one row, and that row ignores the panel height.

    Each was anchored to the bottom of the box it was handed — the same row
    only while this was a 15-row band. A tab is tall enough for the two to
    drift apart by however much the boxes differ.
    """
    positions: set[int] = set()
    for height in (15, 20, 30, 40):
        graph = ContributionGraph(size=(100, height))
        graph.set_commits([_day(0), _day(1, "Ada")])
        surface = Surface(100, height)
        graph.paint(surface)
        rows = ["".join(cell.char for cell in row) for row in surface._rows]

        legend = next(i for i, row in enumerate(rows) if row.startswith("  Less"))
        author_key = next(i for i, row in enumerate(rows) if "*─ Ada" in row)
        stats = next(i for i, row in enumerate(rows) if row.startswith("  Commits "))

        assert legend == author_key
        assert stats == legend + 1
        assert not any(row.strip() for row in rows[stats + 1 :])
        positions.add(legend)
    assert len(positions) == 1, f"legend band drifted with height: {positions}"


def test_legend_follows_the_grid_when_there_is_no_chart():
    """With no series there is no chart legend to share a row with."""
    height = 30
    graph = ContributionGraph(size=(100, height))
    graph.set_commits([])
    surface = Surface(100, height)
    graph.paint(surface)
    rows = ["".join(cell.char for cell in row) for row in surface._rows]

    grid_bottom = _TOP_PAD + _TOP_MARGIN + _HEATMAP_ROWS
    legend = next(i for i, row in enumerate(rows) if row.startswith("  Less"))
    assert legend == grid_bottom


def test_line_chart_legend_keeps_its_row_on_a_taller_surface():
    """``legend_row`` is the chart's own, not the bottom of whatever box it got.

    The contribution graph hands the chart exactly ``total_h`` rows, so the two
    agree there; this pins the widget's side of the contract on its own.
    """
    chart = StepLineChart(plot_w=10, plot_h=3, colors=[(1, 2, 3)], bg=None, title="T")
    chart.set_series({"a": [1, 2, 3], "b": [3, 2, 1]})
    surface = Surface(40, chart.total_h + 10)
    chart.paint(surface)
    rows = ["".join(cell.char for cell in row) for row in surface._rows]

    assert "*─ a" in rows[chart.legend_row]
    assert not any(row.strip() for row in rows[chart.legend_row + 1 :])


def test_build_contribution_calendar_aligns_start_to_monday():
    today = datetime.date(2026, 8, 20)  # Thursday
    calendar = build_contribution_calendar(today, days_back=10)

    assert calendar.today == today
    assert calendar.first_monday.weekday() == 0
    assert calendar.first_monday <= today - datetime.timedelta(days=10)
    assert calendar.num_weeks >= 1


def test_calendar_day_values_maps_counts_and_skips_future():
    today = datetime.date(2026, 8, 20)  # Thursday
    calendar = build_contribution_calendar(today, days_back=6)
    monday = calendar.first_monday
    day_counts = {
        monday: 3,
        monday + datetime.timedelta(days=1): 1,
        today: 5,
    }

    values = calendar_day_values(day_counts, calendar)

    assert values[(0, 0)] == 3
    assert values[(0, 1)] == 1
    assert values[(calendar.num_weeks - 1, today.weekday())] == 5
    assert all(
        monday + datetime.timedelta(weeks=week, days=day) <= today
        for week, day in values
    )
