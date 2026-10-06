"""
Module: tests/app/test_graph_blocks.py
Description: Tests for the self-contained graph blocks on the Graph tab.
Author: Zev
Date: 2026-10-06
"""

from __future__ import annotations

import datetime
from types import SimpleNamespace

import pytest

from pigit.app_graph_blocks import (
    AuthorChart,
    ContributionHeatmap,
    _CELL_CHAR_W,
    _HEATMAP_ROWS,
    _LEFT_MARGIN,
    _TOP_MARGIN,
)
from pigit.termui.surface import Surface


def _day(days_ago: int, author: str = "Zev") -> SimpleNamespace:
    """Minimal commit stand-in: the blocks read only these two attributes."""
    stamp = datetime.datetime.now() - datetime.timedelta(days=days_ago, hours=1)
    return SimpleNamespace(unix_timestamp=int(stamp.timestamp()), author=author)


def _paint(block) -> tuple[list[str], Surface]:
    """Paint *block* at the size it asks for and return its rows."""
    width, height = block.natural_size
    block.resize((width, height))
    surface = Surface(width, height)
    block.paint(surface)
    return ["".join(cell.char for cell in row) for row in surface._rows], surface


class TestContributionHeatmap:
    def test_starts_empty(self):
        heatmap = ContributionHeatmap()
        assert heatmap._day_counts == {}
        assert heatmap._max_count == 0

    def test_natural_size_is_known_before_any_data(self):
        """The layout asks for a size before the first batch arrives."""
        width, height = ContributionHeatmap().natural_size
        assert width > 0
        assert height == _TOP_MARGIN + _HEATMAP_ROWS + 2

    def test_set_commits_counts_days(self):
        heatmap = ContributionHeatmap()
        heatmap.set_commits([_day(0), _day(0, "Ada"), _day(1)])
        assert sum(heatmap._day_counts.values()) == 3
        assert max(heatmap._day_counts.values()) == 2
        assert heatmap._max_count == 2

    def test_add_commits_is_the_same_as_setting_the_whole_list(self):
        """Streamed batches must land on the same counts as one full read."""
        whole = ContributionHeatmap()
        whole.set_commits([_day(0), _day(1), _day(1, "Ada")])

        streamed = ContributionHeatmap()
        streamed.set_commits([_day(0)])
        streamed.add_commits([_day(1), _day(1, "Ada")])

        assert streamed._day_counts == whole._day_counts
        assert streamed._max_count == whole._max_count

    def test_excludes_days_after_today(self):
        """The final partial week stays blank rather than showing '·'."""
        heatmap = ContributionHeatmap()
        _paint(heatmap)
        today = datetime.date.today()
        for week, day in heatmap._heatmap._values:
            date = heatmap._first_monday + datetime.timedelta(weeks=week, days=day)
            assert date <= today

    def test_renders_labels_grid_legend_and_stats(self):
        heatmap = ContributionHeatmap()
        heatmap.set_commits([_day(0), _day(1)])
        rows, _ = _paint(heatmap)

        # Day labels sit in the left margin; the grid's first column starts at
        # column 4, so "Mon" shows as "Mo".
        assert [row[2:4] for row in rows[:6] if row[2:4].strip()] == ["Mo", "We", "Fr"]
        assert any("■" in row for row in rows)
        assert any(row.startswith("  Less") for row in rows)
        assert any(row.startswith("  Commits ") for row in rows)

    def test_legend_sits_directly_under_the_grid(self):
        """The block owns its legend, so nothing else can push it around."""
        heatmap = ContributionHeatmap()
        heatmap.set_commits([_day(0)])
        rows, _ = _paint(heatmap)

        legend = next(i for i, row in enumerate(rows) if row.startswith("  Less"))
        assert legend == _TOP_MARGIN + _HEATMAP_ROWS
        assert rows[legend + 1].startswith("  Commits ")

    def test_current_week_is_marked_by_tint_not_a_frame(self):
        """The marker is the cell tint; the one-sided ``│`` box is gone.

        Week columns are one wide with no gutter, so the box could never be
        drawn on both sides. The right bar was drawn every time — today is
        always in the last week — and the left never, so all you saw was a
        stray vertical line past the last column.
        """
        heatmap = ContributionHeatmap()
        heatmap.set_commits([_day(0)])
        rows, surface = _paint(heatmap)
        assert not any("│" in row for row in rows)

        today_week = (datetime.date.today() - heatmap._first_monday).days // 7
        col = _LEFT_MARGIN + today_week * _CELL_CHAR_W
        grid_rows = range(_TOP_MARGIN, _TOP_MARGIN + _HEATMAP_ROWS)

        def column(c: int):
            return [(surface._rows[r][c].char, surface._rows[r][c].fg) for r in grid_rows]

        assert column(col) != column(col - 1)
        # Tinting must not reach the week before it: with no commits anywhere
        # but today, that column is still drawn in the plain empty colour.
        from pigit.app_theme import THEME

        empty_fg = THEME.contrib_heatmap_colors[0]
        assert {fg for _, fg in column(col - 1)} == {empty_fg}

    def test_tint_skips_a_week_outside_the_calendar(self):
        heatmap = ContributionHeatmap()
        surface = Surface(*heatmap.natural_size)
        heatmap._tint_current_week(
            surface,
            today=datetime.date(2026, 8, 27),
            first_monday=datetime.date(2026, 7, 28),  # today_week >= num_weeks
            num_weeks=4,
            window={},
        )
        from pigit.app_theme import THEME

        assert not any(
            cell.fg == THEME.fg_contrib_week_frame
            for row in surface._rows
            for cell in row
        )


class TestAuthorChart:
    def test_natural_size_is_the_charts_own(self):
        chart = AuthorChart()
        assert chart.natural_size == chart._chart.natural_size

    def test_renders_one_series_per_author(self):
        chart = AuthorChart()
        chart.set_commits([_day(0), _day(1, "Ada")])
        rows, _ = _paint(chart)

        assert any("Commits per Day" in row for row in rows)
        assert any("*─ Ada" in row for row in rows)
        assert any("*─ Zev" in row for row in rows)

    def test_a_quieter_author_drops_out_of_the_series(self):
        chart = AuthorChart()
        chart.set_commits([_day(i, "Zev") for i in range(3)] + [_day(0, "Ada")])
        series = chart._chart._series
        assert set(series) == {"Zev", "Ada"}
        assert sum(series["Zev"]) == 3
        assert sum(series["Ada"]) == 1

    def test_add_commits_matches_setting_the_whole_list(self):
        whole = AuthorChart()
        whole.set_commits([_day(0), _day(1, "Ada")])

        streamed = AuthorChart()
        streamed.set_commits([_day(0)])
        streamed.add_commits([_day(1, "Ada")])

        assert streamed._chart._series == whole._chart._series

    def test_empty_history_draws_nothing(self):
        chart = AuthorChart()
        rows, surface = _paint(chart)
        assert not any(row.strip() for row in rows)


@pytest.mark.parametrize("block_cls", [ContributionHeatmap, AuthorChart])
def test_blocks_ask_for_a_size(block_cls):
    """FlowBoard refuses to place a block that cannot say how big it is."""
    width, height = block_cls().natural_size
    assert width > 0 and height > 0
