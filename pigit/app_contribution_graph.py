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

from pigit.termui import Component, MouseButton, MouseKind, Surface
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
# Graph-area spacing: a separator on the first row, two blank rows on top,
# one blank row at the bottom.
_TOP_PAD = 2
_BOTTOM_PAD = 1
# Columns scrolled per mouse-wheel tick when the combined graph is panned.
_PAN_STEP = 5

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
        size: tuple[int, int] | None = None,
    ) -> None:
        super().__init__(x, y, size)
        self._day_counts: dict[datetime.date, int] = {}
        self._author_day_counts: dict[str, dict[datetime.date, int]] = {}
        self._heatmap = HeatmapGrid(
            rows=7,
            cols=53,
            colors=list(THEME.contrib_heatmap_colors),
            bg=None,
            cell_char=_CELL_CHAR,
            empty_char=_EMPTY_CHAR,
            margin_left=_LEFT_MARGIN,
            margin_top=_TOP_MARGIN,
        )
        self._line_chart = StepLineChart(
            plot_w=55,
            plot_h=7,
            colors=list(THEME.chart_author_colors),
            bg=None,
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
        self._pan_x = 0

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
        calendar = build_contribution_calendar(today)

        self._today = calendar.today
        self._first_monday = calendar.first_monday
        self._num_weeks = calendar.num_weeks
        self._heatmap_values = calendar_day_values(self._day_counts, calendar)
        self._stats = self._calc_stats(calendar.first_monday, calendar.today)
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

    def _draw_stats_horizontal(
        self,
        surface,
        stats: dict[str, int],
        row: int,
    ) -> None:
        """Render summary stats spread side by side on one row."""
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

    def _render_line_chart(
        self,
        surface,
        start_col: int,
        width: int,
        height: int,
    ) -> None:
        """Render the author commit line chart into the right region."""
        if height < self._line_chart.min_size[1]:
            return
        if not self._line_chart_series:
            return

        self._line_chart.set_series(
            self._line_chart_series, x_labels=self._line_chart_labels
        )
        chart_surface = surface.subsurface(0, start_col, width, height)
        self._line_chart.paint(chart_surface)

    def render_into(self, surface) -> None:
        """Public entry to render this graph into the given surface."""
        self.paint(surface)

    def paint(self, surface: Surface) -> None:
        w = min(surface.width, self._size[0] if self._size else surface.width)
        h = min(surface.height, self._size[1] if self._size else surface.height)
        if w <= 0 or h <= 0:
            return

        # No background fill: the graph renders on the panel's own background.

        # Top separator + two blank rows; one blank row reserved at the bottom.
        surface.draw_hline_rgb(0, 0, w, fg=THEME.fg_dim, bg=None)
        content_h = max(1, h - _TOP_PAD - _BOTTOM_PAD)

        today = datetime.date.today()
        if today != self._today:
            self._recompute_derived_data()

        first_monday = self._first_monday
        num_weeks = self._num_weeks

        cell_w = _CELL_CHAR_W
        cell_h = 1

        # Natural layout: the heatmap keeps its full week width and the line
        # chart its minimum width. The chart also needs room for its x-axis
        # labels, which extend past the plot's right edge. The report shows a
        # pannable horizontal window of the combined content instead of
        # compressing either graph.
        chart_w = self._line_chart.min_size[0] + max(
            (len(label) for _, label in self._line_chart_labels), default=0
        )
        gap = 2
        heatmap_w = _PADDING_LEFT + _LEFT_MARGIN + num_weeks * cell_w
        content_w = heatmap_w + gap + chart_w
        max_pan = max(0, content_w - w)
        self._pan_x = max(0, min(self._pan_x, max_pan))
        pan = self._pan_x

        canvas = Surface(content_w, content_h)

        # --- Month labels (row 0) ---
        last_label_end = -1
        for week in range(num_weeks):
            week_start = first_monday + datetime.timedelta(weeks=week)
            if week_start.day <= 7:  # first week of the month
                col = _PADDING_LEFT + _LEFT_MARGIN + week * cell_w
                if col >= last_label_end and col < heatmap_w:
                    label = week_start.strftime("%b")
                    canvas.draw_text_rgb(0, col, label, fg=THEME.fg_muted, bg=None)
                    last_label_end = col + wcswidth(label) + 1

        # --- Day-of-week labels (Mon/Wed/Fri) ---
        day_labels = {0: "Mon", 2: "Wed", 4: "Fri"}
        for day, label in day_labels.items():
            row = _TOP_MARGIN + day * cell_h
            if row < content_h:
                canvas.draw_text_rgb(
                    row, _PADDING_LEFT, label, fg=THEME.fg_muted, bg=None
                )

        # --- Heatmap cells (up to today) ---
        # Cells after today in the final partial week are left out so they
        # render as blank panel background instead of the empty glyph.
        window: dict[tuple[int, int], int] = {}
        for week in range(num_weeks):
            for day in range(7):
                date = first_monday + datetime.timedelta(weeks=week, days=day)
                if date > today:
                    continue
                window[(week, day)] = self._heatmap_values.get((week, day), 0)
        self._heatmap.set_values(window, max_value=self._max_count)
        self._heatmap.resize_grid(cols=num_weeks)
        self._heatmap.paint(canvas)

        # --- Legend (Less → More) near the bottom, stats below it ---
        # Anchored to the content height so a taller report spreads the spacer
        # between the cells and the legend instead of leaving a gap below the
        # stats; the report's bottom blank row is the only empty space.
        legend_row = content_h - 2
        stats_row = content_h - 1
        if legend_row < content_h:
            x = _PADDING_LEFT
            canvas.draw_text_rgb(legend_row, x, "Less", fg=THEME.fg_dim, bg=None)
            x += 5
            for level in range(6):
                ch = _EMPTY_CHAR if level == 0 else _CELL_CHAR
                canvas.draw_text_rgb(
                    legend_row,
                    x,
                    ch,
                    fg=THEME.contrib_heatmap_colors[level],
                    bg=None,
                )
                x += 2
            canvas.draw_text_rgb(legend_row, x, "More", fg=THEME.fg_dim, bg=None)

        # --- Stats (one row below the legend, spread horizontally) ---
        if stats_row < content_h:
            self._draw_stats_horizontal(canvas, self._stats, stats_row)

        # --- Author line chart (right region, full content height) ---
        chart_x = heatmap_w + gap
        if content_h >= self._line_chart.min_size[1]:
            self._render_line_chart(canvas, chart_x, chart_w, content_h)

        # --- Show the pannable window ---
        surface.blit(canvas, 0, pan, w, content_h, _TOP_PAD, 0)

    def handle_mouse(self, event) -> bool:
        """Horizontal wheel over the report pans the combined graph."""
        if event.kind is not MouseKind.PRESS:
            return False
        if event.button is MouseButton.WHEEL_LEFT:
            self._pan_x = max(0, self._pan_x - _PAN_STEP)
            return True
        if event.button is MouseButton.WHEEL_RIGHT:
            self._pan_x += _PAN_STEP
            return True
        return False
