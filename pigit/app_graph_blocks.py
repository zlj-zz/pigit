"""
Module: pigit/app_graph_blocks.py
Description: Self-contained graph blocks for the Graph tab.
Author: Zev
Date: 2026-10-06
"""

from __future__ import annotations

import datetime
import hashlib
from collections import defaultdict

from pigit.termui import Component, Surface, blend
from pigit.termui.primitives import (
    build_contribution_calendar,
    calendar_day_values,
)
from pigit.termui.widgets import HeatmapGrid, StepLineChart
from pigit.termui.wcwidth_table import wcswidth

from .app_theme import THEME

_CELL_CHAR = "■"
_EMPTY_CHAR = "·"
_LEFT_MARGIN = 4
_TOP_MARGIN = 1
_PADDING_LEFT = 2
# Width of the cell character in terminal columns (1 half-width, 2 full-width).
_CELL_CHAR_W = wcswidth(_CELL_CHAR)
# Heatmap rows (Mon→Sun); shared by grid geometry and week highlight.
_HEATMAP_ROWS = 7
# Blend heatmap cell fg toward the week-frame accent (keeps intensity visible).
_WEEK_CELL_FRAME_BLEND = 0.28

# Rows the heatmap block spends besides the grid: month labels above it, and
# the scale legend plus the stats line below it. The legend sits directly
# under the grid — this block owns it, so there is no other graph's row to
# line up with.
_LEGEND_ROWS = 2

# Author chart geometry.
_PLOT_W = 55
_PLOT_H = 7
_CHART_DAYS = 30
_CHART_AUTHORS = 6

# Punch card geometry: one row per weekday, one column per hour.
_WEEKDAYS = 7
_HOURS = 24
_TITLE_ROWS = 1
_HOUR_LABEL_ROWS = 1
# Hour labels worth printing; the gaps between them are six columns wide, so
# the two-digit ones cannot run into the next.
_LABELLED_HOURS = (0, 6, 12, 18)
# Rows above the grid: the title, then the hour labels.
_GRID_TOP = _TITLE_ROWS + _HOUR_LABEL_ROWS


def _author_chart_color(author: str) -> tuple[int, int, int]:
    """Stable series color from author name (hash into chart_author_colors)."""
    colors = THEME.chart_author_colors
    digest = hashlib.md5(author.encode("utf-8")).digest()
    idx = int.from_bytes(digest[:4], "big") % len(colors)
    return colors[idx]


def _commit_day(commit) -> datetime.date:
    """Local date a commit landed on."""
    return datetime.datetime.fromtimestamp(commit.unix_timestamp).date()


def _commit_slot(commit) -> tuple[int, int]:
    """``(hour, weekday)`` a commit landed in, in local time."""
    stamp = datetime.datetime.fromtimestamp(commit.unix_timestamp)
    return (stamp.hour, stamp.weekday())


class ContributionHeatmap(Component):
    """One year of daily commit activity, with its own legend and stats.

    Each cell is one day; columns are weeks (Mon→Sun, top-to-bottom). Color
    intensity maps to the number of commits on that day.
    """

    def __init__(
        self,
        x: int = 1,
        y: int = 1,
        size: tuple[int, int] | None = None,
    ) -> None:
        super().__init__(x, y, size)
        self._day_counts: dict[datetime.date, int] = {}
        self._max_count = 0
        self._heatmap = HeatmapGrid(
            rows=_HEATMAP_ROWS,
            cols=53,
            colors=list(THEME.contrib_heatmap_colors),
            bg=None,
            cell_char=_CELL_CHAR,
            empty_char=_EMPTY_CHAR,
            margin_left=_LEFT_MARGIN,
            margin_top=_TOP_MARGIN,
        )
        self._today: datetime.date = datetime.date.min
        self._first_monday: datetime.date = datetime.date.min
        self._num_weeks = 0
        self._heatmap_values: dict[tuple[int, int], int] = {}
        self._stats: dict[str, int] = {}
        # The calendar follows today's date, not the commits, so it is valid
        # from construction: natural_size has to mean something before any
        # data arrives or a layout cannot place this block.
        self._refresh_calendar()

    @property
    def _natural_width(self) -> int:
        """Columns the week grid and its labels occupy."""
        return _PADDING_LEFT + _LEFT_MARGIN + self._num_weeks * _CELL_CHAR_W

    @property
    def natural_size(self) -> tuple[int, int]:
        """Every week column wide, labels + grid + legend + stats tall."""
        return (
            self._natural_width,
            _TOP_MARGIN + _HEATMAP_ROWS + _LEGEND_ROWS,
        )

    def set_commits(self, commits: list) -> None:
        """Rebuild the daily counts from a full commit list."""
        counts: dict[datetime.date, int] = defaultdict(int)
        for commit in commits:
            counts[_commit_day(commit)] += 1
        self._day_counts = dict(counts)
        self._max_count = max(counts.values()) if counts else 0
        self._refresh_calendar()

    def add_commits(self, commits: list) -> None:
        """Add commits to the tallies (counts only ever grow, so adding is exact)."""
        for commit in commits:
            day = _commit_day(commit)
            count = self._day_counts.get(day, 0) + 1
            self._day_counts[day] = count
            self._max_count = max(self._max_count, count)
        self._refresh_calendar()

    def _refresh_calendar(self) -> None:
        """Recompute everything derived from the counts and today's date."""
        calendar = build_contribution_calendar(datetime.date.today())
        self._today = calendar.today
        self._first_monday = calendar.first_monday
        self._num_weeks = calendar.num_weeks
        self._heatmap_values = calendar_day_values(self._day_counts, calendar)
        self._stats = self._calc_stats(calendar.first_monday, calendar.today)

    def _calc_stats(
        self, first_monday: datetime.date, today: datetime.date
    ) -> dict[str, int]:
        """Compute summary statistics for the displayed period."""
        total = sum(self._day_counts.values())
        active = sum(1 for c in self._day_counts.values() if c > 0)
        max_daily = max(self._day_counts.values()) if self._day_counts else 0

        # Current streak: count backwards from today while commits > 0
        current_streak = 0
        d = today
        while d >= first_monday:
            if self._day_counts.get(d, 0) > 0:
                current_streak += 1
                d -= datetime.timedelta(days=1)
            else:
                break

        # Longest streak
        longest_streak = 0
        current = 0
        days_total = (today - first_monday).days + 1
        for i in range(days_total):
            d = first_monday + datetime.timedelta(days=i)
            if self._day_counts.get(d, 0) > 0:
                current += 1
                longest_streak = max(longest_streak, current)
            else:
                current = 0

        return {
            "total": total,
            "active": active,
            "current_streak": current_streak,
            "longest_streak": longest_streak,
            "max_daily": max_daily,
        }

    def paint(self, surface: Surface) -> None:
        if datetime.date.today() != self._today:
            self._refresh_calendar()

        first_monday = self._first_monday
        num_weeks = self._num_weeks
        heatmap_w = self._natural_width

        self._draw_month_labels(surface, first_monday, num_weeks, heatmap_w)
        self._draw_day_labels(surface)
        self._draw_cells(surface, first_monday, num_weeks)

        legend_row = _TOP_MARGIN + _HEATMAP_ROWS
        self._draw_legend(surface, legend_row)
        self._draw_stats_horizontal(surface, self._stats, legend_row + 1)

    def _draw_month_labels(
        self,
        surface: Surface,
        first_monday: datetime.date,
        num_weeks: int,
        heatmap_w: int,
    ) -> None:
        """Month labels on row 0, one per month, spaced so they never touch."""
        last_label_end = -1
        for week in range(num_weeks):
            week_start = first_monday + datetime.timedelta(weeks=week)
            if week_start.day > 7:  # not the first week of the month
                continue
            col = _PADDING_LEFT + _LEFT_MARGIN + week * _CELL_CHAR_W
            if col >= last_label_end and col < heatmap_w:
                label = week_start.strftime("%b")
                surface.draw_text_rgb(0, col, label, fg=THEME.fg_muted, bg=None)
                last_label_end = col + wcswidth(label) + 1

    def _draw_day_labels(self, surface: Surface) -> None:
        """Day-of-week labels (Mon/Wed/Fri) down the left margin."""
        for day, label in {0: "Mon", 2: "Wed", 4: "Fri"}.items():
            row = _TOP_MARGIN + day
            if row < surface.height:
                surface.draw_text_rgb(
                    row, _PADDING_LEFT, label, fg=THEME.fg_muted, bg=None
                )

    def _draw_cells(
        self,
        surface: Surface,
        first_monday: datetime.date,
        num_weeks: int,
    ) -> dict[tuple[int, int], int]:
        """Draw the week grid and tint the current week; return the window drawn.

        Cells after today in the final partial week are left out so they render
        as blank background instead of the empty glyph.
        """
        today = self._today
        window: dict[tuple[int, int], int] = {}
        for week in range(num_weeks):
            for day in range(_HEATMAP_ROWS):
                date = first_monday + datetime.timedelta(weeks=week, days=day)
                if date > today:
                    continue
                window[(week, day)] = self._heatmap_values.get((week, day), 0)
        self._heatmap.set_values(window, max_value=self._max_count)
        self._heatmap.resize_grid(cols=num_weeks)
        self._heatmap.paint(surface)
        self._tint_current_week(
            surface,
            today=today,
            first_monday=first_monday,
            num_weeks=num_weeks,
            window=window,
        )
        return window

    def _draw_legend(self, surface: Surface, row: int) -> None:
        """The ``Less → More`` scale, directly under the grid."""
        if row >= surface.height:
            return
        surface.draw_text_rgb(row, _PADDING_LEFT, "Less", fg=THEME.fg_dim, bg=None)
        x = _PADDING_LEFT + 5
        for level in range(6):
            ch = _EMPTY_CHAR if level == 0 else _CELL_CHAR
            surface.draw_text_rgb(
                row, x, ch, fg=THEME.contrib_heatmap_colors[level], bg=None
            )
            x += 2
        surface.draw_text_rgb(row, x, "More", fg=THEME.fg_dim, bg=None)

    def _draw_stats_horizontal(
        self,
        surface: Surface,
        stats: dict[str, int],
        row: int,
    ) -> None:
        """Render summary stats spread side by side on one row."""
        if row >= surface.height:
            return
        items = [
            ("Commits", str(stats["total"])),
            ("Active", f"{stats['active']}d"),
            ("Streak", str(stats["current_streak"])),
            ("Best", str(stats["longest_streak"])),
            ("Peak", str(stats["max_daily"])),
        ]
        x = _PADDING_LEFT
        for label, value in items:
            text = f"{label} {value}"
            surface.draw_text_rgb(row, x, text, fg=THEME.fg_muted, bg=None)
            x += wcswidth(text) + 3

    def _tint_current_week(
        self,
        surface: Surface,
        *,
        today: datetime.date,
        first_monday: datetime.date,
        num_weeks: int,
        window: dict[tuple[int, int], int],
    ) -> None:
        """Tint the current week's elapsed days toward ``fg_contrib_week_frame``.

        Cells only, no box: week columns are one wide with no gutter, so a
        frame could never be drawn on both sides. The right bar was drawn every
        time (today is always in the last week) and the left never, which read
        as a stray vertical border on the heatmap's right edge.
        """
        today_week = (today - first_monday).days // 7
        if today_week < 0 or today_week >= num_weeks:
            return

        col_start = _LEFT_MARGIN + today_week * _CELL_CHAR_W
        frame_fg = THEME.fg_contrib_week_frame
        color_fn = self._heatmap._color_fn

        for day in range(_HEATMAP_ROWS):
            row = _TOP_MARGIN + day
            if row >= surface.height:
                continue
            date = first_monday + datetime.timedelta(weeks=today_week, days=day)
            if date > today:
                continue
            value = window.get((today_week, day), 0)
            base_fg = color_fn(value, self._max_count)
            ch = _CELL_CHAR if value > 0 else _EMPTY_CHAR
            tint_fg = blend(base_fg, frame_fg, _WEEK_CELL_FRAME_BLEND)
            surface.draw_text_rgb(row, col_start, ch, fg=tint_fg, bg=None)


class AuthorChart(Component):
    """Daily commits for the busiest authors over the last month."""

    def __init__(
        self,
        x: int = 1,
        y: int = 1,
        size: tuple[int, int] | None = None,
    ) -> None:
        super().__init__(x, y, size)
        self._author_day_counts: dict[str, dict[datetime.date, int]] = defaultdict(
            dict
        )
        self._chart = StepLineChart(
            plot_w=_PLOT_W,
            plot_h=_PLOT_H,
            colors=list(THEME.chart_author_colors),
            bg=None,
            title="Commits per Day",
            title_fg=THEME.fg_primary,
            label_fg=THEME.fg_muted,
            axis_fg=THEME.fg_dim,
            padding_left=_PADDING_LEFT,
        )

    @property
    def natural_size(self) -> tuple[int, int]:
        """Whatever the chart needs to draw every label it has."""
        return self._chart.natural_size

    def set_commits(self, commits: list) -> None:
        """Rebuild the per-author daily counts from a full commit list."""
        counts: dict[str, dict[datetime.date, int]] = defaultdict(
            lambda: defaultdict(int)
        )
        for commit in commits:
            counts[commit.author][_commit_day(commit)] += 1
        self._author_day_counts = {
            author: dict(days) for author, days in counts.items()
        }
        self._rebuild_series()

    def add_commits(self, commits: list) -> None:
        """Add commits to the per-author tallies (counts only ever grow)."""
        for commit in commits:
            day = _commit_day(commit)
            days = self._author_day_counts.setdefault(commit.author, {})
            days[day] = days.get(day, 0) + 1
        self._rebuild_series()

    def _rebuild_series(self) -> None:
        """Rebuild the chart's series and x-axis labels from the tallies."""
        today = datetime.date.today()
        start_date = today - datetime.timedelta(days=_CHART_DAYS)

        author_totals = {
            author: sum(days.values())
            for author, days in self._author_day_counts.items()
        }
        top_authors = sorted(
            author_totals.items(), key=lambda item: item[1], reverse=True
        )[:_CHART_AUTHORS]
        authors = [author for author, _ in top_authors]
        if not authors:
            self._chart.set_series({})
            return

        series: dict[str, list[int]] = {}
        for author in authors:
            days = self._author_day_counts.get(author, {})
            series[author] = [
                days.get(start_date + datetime.timedelta(days=i), 0)
                for i in range(_CHART_DAYS + 1)
            ]

        self._chart.set_series(
            series,
            x_labels=[
                (0, start_date.strftime("%b %d")),
                (
                    _PLOT_W // 2,
                    (start_date + datetime.timedelta(days=_CHART_DAYS // 2)).strftime(
                        "%b %d"
                    ),
                ),
                (_PLOT_W - 1, today.strftime("%b %d")),
            ],
            series_colors={author: _author_chart_color(author) for author in series},
        )

    def paint(self, surface: Surface) -> None:
        self._chart.resize((surface.width, surface.height))
        self._chart.paint(surface)


class PunchCard(Component):
    """Commits by weekday and hour: when the work actually happens.

    The calendar heatmap answers *which day*; this answers *what time of day*,
    which is a different question about the same commits.
    """

    def __init__(
        self,
        x: int = 1,
        y: int = 1,
        size: tuple[int, int] | None = None,
    ) -> None:
        super().__init__(x, y, size)
        # {(hour, weekday): count} -- HeatmapGrid addresses cells as (col, row).
        self._hour_counts: dict[tuple[int, int], int] = {}
        self._max_count = 0
        self._grid = HeatmapGrid(
            rows=_WEEKDAYS,
            cols=_HOURS,
            colors=list(THEME.contrib_heatmap_colors),
            bg=None,
            cell_char=_CELL_CHAR,
            empty_char=_EMPTY_CHAR,
            margin_left=_PADDING_LEFT + _LEFT_MARGIN,
            margin_top=_GRID_TOP,
        )

    @property
    def natural_size(self) -> tuple[int, int]:
        """Every hour column wide, title + labels + one row per weekday tall."""
        return (
            _PADDING_LEFT + _LEFT_MARGIN + _HOURS * _CELL_CHAR_W,
            _GRID_TOP + _WEEKDAYS,
        )

    def set_commits(self, commits: list) -> None:
        """Rebuild the weekday-by-hour counts from a full commit list."""
        counts: dict[tuple[int, int], int] = defaultdict(int)
        for commit in commits:
            counts[_commit_slot(commit)] += 1
        self._hour_counts = dict(counts)
        self._max_count = max(counts.values()) if counts else 0

    def add_commits(self, commits: list) -> None:
        """Add commits to the tallies (counts only ever grow, so adding is exact)."""
        for commit in commits:
            slot = _commit_slot(commit)
            count = self._hour_counts.get(slot, 0) + 1
            self._hour_counts[slot] = count
            self._max_count = max(self._max_count, count)

    def paint(self, surface: Surface) -> None:
        surface.draw_text_rgb(
            0,
            _PADDING_LEFT,
            "Commits by Hour",
            fg=THEME.fg_primary,
            bg=None,
        )
        label_row = _TITLE_ROWS
        for hour in _LABELLED_HOURS:
            col = _PADDING_LEFT + _LEFT_MARGIN + hour * _CELL_CHAR_W
            surface.draw_text_rgb(
                label_row, col, str(hour), fg=THEME.fg_muted, bg=None
            )
        for weekday, label in {0: "Mon", 2: "Wed", 4: "Fri"}.items():
            surface.draw_text_rgb(
                _GRID_TOP + weekday,
                _PADDING_LEFT,
                label,
                fg=THEME.fg_muted,
                bg=None,
            )
        self._grid.set_values(self._hour_counts, max_value=self._max_count)
        self._grid.paint(surface)
