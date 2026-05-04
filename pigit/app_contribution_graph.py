# -*- coding: utf-8 -*-
"""
Module: pigit/app_contribution_graph.py
Description: GitHub-style contribution heatmap for commit history.

Each cell = one day; columns are weeks (Mon→Sun top-to-bottom).
Color intensity maps to daily commit count.
Author: Zev
Date: 2026-04-25
"""

from __future__ import annotations

import datetime
from collections import defaultdict
from typing import Optional

from pigit.termui import Component, HeatmapGrid, StepLineChart, palette
from pigit.termui.wcwidth_table import wcswidth

from .app_theme import THEME


_GRAPH_BG = (45, 45, 50)

# GitHub-style green heatmap palette (0 → 5)
# Level 0 is intentionally lighter than _GRAPH_BG so empty cells pop.
_HEATMAP_COLORS: list[tuple[int, int, int]] = [
    (100, 100, 110),  # 0 commits (muted, not dim)
    (155, 233, 168),  # level 1 (lightest green)
    (105, 210, 130),  # level 2 (light green)
    (64, 196, 99),  # level 3 (medium green)
    (48, 161, 78),  # level 4 (dark green)
    (33, 110, 57),  # level 5 (very dark green)
]

# Author line chart colors (top 6 authors)
_AUTHOR_COLORS: list[tuple[int, int, int]] = [
    THEME.accent_cyan,
    THEME.accent_yellow,
    THEME.accent_purple,
    THEME.accent_red,
    THEME.accent_green,
    THEME.accent_blue,
]

_CELL_CHAR = "■"
_EMPTY_CHAR = "·"
_LEFT_MARGIN = 4
_TOP_MARGIN = 1
_PADDING_LEFT = 2

# Width of the cell character in terminal columns (1 for half-width, 2 for full-width)
_CELL_CHAR_W = wcswidth(_CELL_CHAR)


class ContributionGraph(Component):
    """GitHub-style contribution heatmap.

    Shows roughly one year of daily commit activity.
    Each cell is one day; columns are weeks (Mon→Sun, top-to-bottom).
    Color intensity maps to the number of commits on that day.
    """

    def __init__(
        self,
        x: int = 1,
        y: int = 1,
        size: Optional[tuple[int, int]] = None,
    ) -> None:
        super().__init__(x, y, size)
        self._day_counts: dict[datetime.date, int] = {}
        self._author_day_counts: dict[str, dict[datetime.date, int]] = {}
        self._heatmap = HeatmapGrid(
            rows=7,
            cols=53,
            colors=_HEATMAP_COLORS,
            bg=_GRAPH_BG,
            cell_char=_CELL_CHAR,
            empty_char=_EMPTY_CHAR,
            margin_left=_LEFT_MARGIN,
            margin_top=_TOP_MARGIN,
        )
        self._line_chart = StepLineChart(
            plot_w=55,
            plot_h=7,
            colors=_AUTHOR_COLORS,
            bg=_GRAPH_BG,
            title="Commits per Day",
            title_fg=THEME.fg_primary,
            label_fg=THEME.fg_muted,
            axis_fg=THEME.fg_dim,
            padding_left=_PADDING_LEFT,
        )
        # Pre-computed derived data (invalidated when date changes)
        self._today: datetime.date = datetime.date.min
        self._first_monday: datetime.date = datetime.date.min
        self._num_weeks = 0
        self._heatmap_values: dict[tuple[int, int], int] = {}
        self._stats: dict[str, int] = {}
        self._line_chart_series: dict[str, list[int]] = {}
        self._line_chart_labels: list[tuple[int, str]] = []
        self._max_count = 0

    def min_height(self) -> int:
        """Return minimum rows needed to render heatmap + line chart."""
        # heatmap: month labels + 7 days + legend = 10
        # gap: 1
        # line chart: title(1) + plot(7) + x-axis(2) + legend(2) = 12
        return _TOP_MARGIN + 7 + 2 + 1 + 12

    def set_commits(self, commits: list) -> None:
        """Build daily commit counts and per-author counts from the given commit list."""
        counts = defaultdict(int)
        author_counts: dict[str, dict[datetime.date, int]] = defaultdict(
            lambda: defaultdict(int)
        )
        for c in commits:
            dt = datetime.datetime.fromtimestamp(c.unix_timestamp)
            d = dt.date()
            counts[d] += 1
            author_counts[c.author][d] += 1
        self._day_counts = dict(counts)
        self._author_day_counts = {
            author: dict(dates) for author, dates in author_counts.items()
        }
        self._max_count = max(counts.values()) if counts else 0
        self._recompute_derived_data()

    def _recompute_derived_data(self) -> None:
        """Pre-compute all derived data that depends on commit counts and current date."""
        today = datetime.date.today()
        start = today - datetime.timedelta(days=365)
        # Align to the previous Monday so weeks line up nicely.
        first_monday = start - datetime.timedelta(days=start.weekday())
        days = (today - first_monday).days + 1
        num_weeks = (days + 6) // 7

        self._today = today
        self._first_monday = first_monday
        self._num_weeks = num_weeks

        # Pre-compute heatmap values
        self._heatmap_values = {}
        for week in range(num_weeks):
            for day in range(7):
                date = first_monday + datetime.timedelta(weeks=week, days=day)
                if date > today:
                    continue
                self._heatmap_values[(week, day)] = self._day_counts.get(date, 0)

        # Pre-compute stats
        self._stats = self._calc_stats(first_monday, today)

        # Pre-compute line chart data
        self._recompute_line_chart_data(today)

    def _recompute_line_chart_data(self, today: datetime.date) -> None:
        """Pre-compute author series and x-axis labels for the line chart."""
        days_back = 30
        start_date = today - datetime.timedelta(days=days_back)

        # Top authors by total commits
        author_totals = {
            author: sum(dates.values())
            for author, dates in self._author_day_counts.items()
        }
        top_authors = sorted(
            author_totals.items(),
            key=lambda x: x[1],
            reverse=True,
        )[:6]
        authors = [a for a, _ in top_authors]
        if not authors:
            self._line_chart_series = {}
            self._line_chart_labels = []
            return

        # Build per-author series
        author_series: dict[str, list[int]] = {}
        for author in authors:
            series = []
            for i in range(days_back + 1):
                d = start_date + datetime.timedelta(days=i)
                count = self._author_day_counts.get(author, {}).get(d, 0)
                series.append(count)
            author_series[author] = series

        # X-axis labels
        x_labels = [
            (0, start_date.strftime("%b %d")),
            (
                self._line_chart._plot_w // 2,
                (start_date + datetime.timedelta(days=days_back // 2)).strftime(
                    "%b %d"
                ),
            ),
            (self._line_chart._plot_w - 1, today.strftime("%b %d")),
        ]

        self._line_chart_series = author_series
        self._line_chart_labels = x_labels

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

    def _draw_stats(
        self,
        surface,
        stats: dict[str, int],
        start_col: int,
        start_row: int,
        max_h: int,
    ) -> None:
        """Render summary stats to the right of the heatmap."""
        items = [
            ("Commits", str(stats["total"])),
            ("Active", f"{stats['active']} days"),
            ("Streak", str(stats["current_streak"])),
            ("Best", str(stats["longest_streak"])),
            ("Peak", str(stats["max_daily"])),
        ]
        for i, (label, value) in enumerate(items):
            row = start_row + i
            if row >= max_h:
                break
            surface.draw_text_rgb(
                row, start_col, label, fg=THEME.fg_muted, bg=_GRAPH_BG
            )
            surface.draw_text_rgb(
                row, start_col + 10, value, fg=THEME.fg_primary, bg=_GRAPH_BG
            )

    def _render_line_chart(
        self,
        surface,
        start_row: int,
        width: int,
        height: int,
    ) -> None:
        """Render author commit line chart via StepLineChart."""
        if height < self._line_chart.min_size[1]:
            return
        if not self._line_chart_series:
            return

        self._line_chart.set_series(
            self._line_chart_series, x_labels=self._line_chart_labels
        )
        chart_surface = surface.subsurface(start_row, 0, width, height)
        self._line_chart._render_surface(chart_surface)

    def render_into(self, surface) -> None:
        """Public entry to render this graph into the given surface."""
        self._render_surface(surface)

    def _render_surface(self, surface) -> None:
        w = min(surface.width, self._size[0] if self._size else surface.width)
        h = min(surface.height, self._size[1] if self._size else surface.height)
        if w <= 0 or h <= 0:
            return

        surface.fill_rect_rgb(0, 0, w, h, _GRAPH_BG)

        today = datetime.date.today()
        if today != self._today:
            self._recompute_derived_data()

        first_monday = self._first_monday
        num_weeks = self._num_weeks

        # Tight layout: no gaps between columns.
        cell_w = _CELL_CHAR_W
        cell_h = 1

        # --- Month labels (row 0) ---
        last_label_end = -1
        for week in range(num_weeks):
            week_start = first_monday + datetime.timedelta(weeks=week)
            if week_start.day <= 7:  # first week of the month
                col = _PADDING_LEFT + _LEFT_MARGIN + week * cell_w
                if col >= last_label_end and col < w:
                    label = week_start.strftime("%b")
                    surface.draw_text_rgb(
                        0, col, label, fg=THEME.fg_muted, bg=_GRAPH_BG
                    )
                    last_label_end = col + wcswidth(label) + 1

        # --- Day-of-week labels (Mon/Wed/Fri) ---
        day_labels = {0: "Mon", 2: "Wed", 4: "Fri"}
        for day, label in day_labels.items():
            row = _TOP_MARGIN + day * cell_h
            if row < h:
                surface.draw_text_rgb(
                    row, _PADDING_LEFT, label, fg=THEME.fg_muted, bg=_GRAPH_BG
                )

        # --- Heatmap cells ---
        self._heatmap.set_values(
            self._heatmap_values,
            max_value=self._max_count,
        )
        self._heatmap.resize(cols=num_weeks)
        self._heatmap._render_surface(surface)

        # --- Legend (Less → More) ---
        legend_row = _TOP_MARGIN + 7 * cell_h + 1
        if legend_row < h:
            x = _PADDING_LEFT
            surface.draw_text_rgb(legend_row, x, "Less", fg=THEME.fg_dim, bg=_GRAPH_BG)
            x += 5
            for level in range(6):
                ch = _EMPTY_CHAR if level == 0 else _CELL_CHAR
                surface.draw_text_rgb(
                    legend_row,
                    x,
                    ch,
                    fg=_HEATMAP_COLORS[level],
                    bg=_GRAPH_BG,
                )
                x += 2
            surface.draw_text_rgb(legend_row, x, "More", fg=THEME.fg_dim, bg=_GRAPH_BG)

        # --- Stats (right of heatmap) ---
        stats_col = _PADDING_LEFT + _LEFT_MARGIN + num_weeks * cell_w + 3
        if stats_col + 16 < w:
            self._draw_stats(
                surface, self._stats, stats_col, _TOP_MARGIN, _TOP_MARGIN + 7
            )

        # --- Author line chart ---
        chart_start_row = _TOP_MARGIN + 7 + 2 + 1  # after heatmap + legend + gap
        chart_h = h - chart_start_row
        if chart_h >= 12:
            self._render_line_chart(surface, chart_start_row, w, chart_h)
