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
import math
from collections import defaultdict
from typing import Optional

from pigit.termui import Component, palette
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

    def _color_for(self, count: int) -> tuple[int, int, int]:
        """Return heatmap color for a given daily commit count.

        Uses a log scale so low-commit days still show visible
        progression instead of being crushed by a single high-commit day.
        """
        if count == 0:
            return _HEATMAP_COLORS[0]
        if self._max_count <= 1:
            return _HEATMAP_COLORS[1]
        # Map count (1..max) to level (1..5) on a log scale.
        ratio = math.log(count) / math.log(self._max_count)
        level = max(1, min(5, int(ratio * 4) + 1))
        return _HEATMAP_COLORS[level]

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
        """Render author commit line chart with fixed dimensions."""
        # Fixed dimensions
        plot_w = 55
        plot_h = 7
        title_h = 1
        x_axis_h = 2
        legend_h = 2

        # Check minimum space
        total_h = title_h + plot_h + x_axis_h + legend_h
        if height < total_h:
            return

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
            return

        today = datetime.date.today()
        days_back = 30
        start_date = today - datetime.timedelta(days=days_back)

        # Title
        surface.draw_text_rgb(
            start_row,
            _PADDING_LEFT,
            "Commits per Day",
            fg=THEME.fg_primary,
            bg=_GRAPH_BG,
            style_flags=palette.STYLE_BOLD,
        )

        # Build per-author series
        author_series: dict[str, list[int]] = {}
        overall_max = 0
        for author in authors:
            series = []
            for i in range(days_back + 1):
                d = start_date + datetime.timedelta(days=i)
                count = self._author_day_counts.get(author, {}).get(d, 0)
                series.append(count)
                overall_max = max(overall_max, count)
            author_series[author] = series

        if overall_max == 0:
            return

        chart_top = start_row + title_h
        chart_bottom = chart_top + plot_h - 1

        # Y-axis layout
        y_axis_label_w = 5
        y_axis_col = _PADDING_LEFT + y_axis_label_w

        # Y-axis labels (one per horizontal grid line, top to bottom)
        for i in range(plot_h):
            row = chart_top + i
            value = int(round(overall_max * (plot_h - 1 - i) / (plot_h - 1)))
            label = str(value)
            # right-align within y_axis_label_w
            pad = max(0, y_axis_label_w - len(label))
            surface.draw_text_rgb(
                row, _PADDING_LEFT + pad, label, fg=THEME.fg_muted, bg=_GRAPH_BG
            )

        # Y-axis line with ticks: ┤ for ticks, ┼ for origin
        for r in range(chart_top, chart_bottom + 1):
            if r == chart_bottom:
                surface.draw_text_rgb(r, y_axis_col, "┼", fg=THEME.fg_dim, bg=_GRAPH_BG)
            else:
                surface.draw_text_rgb(r, y_axis_col, "┤", fg=THEME.fg_dim, bg=_GRAPH_BG)

        # X-axis line
        x_axis_row = chart_bottom
        surface.draw_text_rgb(
            x_axis_row, y_axis_col + 1, "─" * plot_w, fg=THEME.fg_dim, bg=_GRAPH_BG
        )

        # X-axis date labels
        label_dates = [
            start_date,
            start_date + datetime.timedelta(days=days_back // 2),
            today,
        ]
        for d in label_dates:
            day_offset = (d - start_date).days
            col = y_axis_col + 1 + int(day_offset * plot_w / (days_back + 1))
            label = d.strftime("%b %d")
            if col + len(label) <= width:
                surface.draw_text_rgb(
                    x_axis_row + 1, col, label, fg=THEME.fg_muted, bg=_GRAPH_BG
                )

        # Draw lines (uniformly mapped to plot_w columns)
        for aidx, author in enumerate(authors):
            color = _AUTHOR_COLORS[aidx % len(_AUTHOR_COLORS)]
            series = author_series[author]

            # Map data points uniformly onto plot_w columns
            num_points = len(series)
            mapped_rows: list[int] = []
            for c in range(plot_w):
                idx = min(int(c * num_points / plot_w), num_points - 1)
                count = series[idx]
                row = chart_bottom - int((count / overall_max) * (plot_h - 1))
                mapped_rows.append(row)

            # First pass: horizontal platforms on every column
            for c in range(plot_w):
                row = mapped_rows[c]
                col = y_axis_col + 1 + c
                surface.draw_text_rgb(row, col, "─", fg=color, bg=_GRAPH_BG)

            # Second pass: rounded step connections at column boundaries
            for c in range(plot_w - 1):
                row = mapped_rows[c]
                next_row = mapped_rows[c + 1]
                col = y_axis_col + 1 + c + 1
                if next_row < row:  # ascending (next point is higher)
                    surface.draw_text_rgb(row, col, "╯", fg=color, bg=_GRAPH_BG)
                    for r in range(next_row + 1, row):
                        surface.draw_text_rgb(r, col, "│", fg=color, bg=_GRAPH_BG)
                    surface.draw_text_rgb(next_row, col, "╭", fg=color, bg=_GRAPH_BG)
                elif next_row > row:  # descending (next point is lower)
                    surface.draw_text_rgb(row, col, "╮", fg=color, bg=_GRAPH_BG)
                    for r in range(row + 1, next_row):
                        surface.draw_text_rgb(r, col, "│", fg=color, bg=_GRAPH_BG)
                    surface.draw_text_rgb(next_row, col, "╰", fg=color, bg=_GRAPH_BG)

        # Legend
        legend_row = x_axis_row + 2
        x = _PADDING_LEFT
        for aidx, author in enumerate(authors):
            color = _AUTHOR_COLORS[aidx % len(_AUTHOR_COLORS)]
            name = author[:10]
            entry_width = 2 + len(name) + 3
            if x + entry_width > width:
                break
            surface.draw_text_rgb(legend_row, x, "*", fg=color, bg=_GRAPH_BG)
            x += 2
            surface.draw_text_rgb(legend_row, x, name, fg=THEME.fg_muted, bg=_GRAPH_BG)
            x += len(name) + 3

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
        start = today - datetime.timedelta(days=365)
        # Align to the previous Monday so weeks line up nicely.
        first_monday = start - datetime.timedelta(days=start.weekday())

        days = (today - first_monday).days + 1
        num_weeks = (days + 6) // 7

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
        for week in range(num_weeks):
            for day in range(7):
                date = first_monday + datetime.timedelta(weeks=week, days=day)
                if date > today:
                    continue

                col = _LEFT_MARGIN + week * cell_w
                row = _TOP_MARGIN + day * cell_h
                if col >= w or row >= h:
                    continue

                count = self._day_counts.get(date, 0)
                color = self._color_for(count)
                ch = _CELL_CHAR if count > 0 else _EMPTY_CHAR
                surface.draw_text_rgb(row, col, ch, fg=color, bg=_GRAPH_BG)

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
            stats = self._calc_stats(first_monday, today)
            self._draw_stats(surface, stats, stats_col, _TOP_MARGIN, _TOP_MARGIN + 7)

        # --- Author line chart ---
        chart_start_row = _TOP_MARGIN + 7 + 2 + 1  # after heatmap + legend + gap
        chart_h = h - chart_start_row
        if chart_h >= 12:
            self._render_line_chart(surface, chart_start_row, w, chart_h)
