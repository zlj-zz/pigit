# -*- coding: utf-8 -*-
"""
Module: pigit/termui/_component_graph.py
Description: Generic heatmap grid and stepped line chart components.
Author: Zev
Date: 2026-04-30
"""

from __future__ import annotations

import math
from typing import Callable, Optional

from . import palette
from ._component_base import Component
from .wcwidth_table import wcswidth

# Box-drawing characters
_BOX_H = "─"
_BOX_V = "│"
_BOX_CROSS = "┼"
_BOX_TICK = "┤"
_BOX_CORNER_TL = "╭"
_BOX_CORNER_TR = "╮"
_BOX_CORNER_BR = "╯"
_BOX_CORNER_BL = "╰"


class HeatmapGrid(Component):
    """Generic grid heatmap: maps (col, row) intensity values to colored cells.

    No calendar or axis semantics — purely a visual cell grid with a
    configurable color mapping. Can be used standalone or embedded inside
    another component.
    """

    def __init__(
        self,
        x: int = 1,
        y: int = 1,
        size: Optional[tuple[int, int]] = None,
        *,
        rows: int = 7,
        cols: int = 53,
        colors: list[tuple[int, int, int]],
        bg: tuple[int, int, int],
        cell_char: str = "■",
        empty_char: str = "·",
        margin_left: int = 0,
        margin_top: int = 0,
        color_fn: Optional[Callable[[int, int], tuple[int, int, int]]] = None,
    ) -> None:
        super().__init__(x, y, size)
        self._rows = rows
        self._cols = cols
        self._colors = colors
        self._bg = bg
        self._cell_char = cell_char
        self._empty_char = empty_char
        self._margin_left = margin_left
        self._margin_top = margin_top
        self._color_fn = color_fn or self._default_color_for
        self._values: dict[tuple[int, int], int] = {}
        self._max_value = 0

    def resize(
        self,
        rows: Optional[int] = None,
        cols: Optional[int] = None,
    ) -> None:
        """Resize the grid geometry."""
        if rows is not None:
            self._rows = rows
        if cols is not None:
            self._cols = cols

    def set_values(
        self,
        values: dict[tuple[int, int], int],
        max_value: Optional[int] = None,
    ) -> None:
        """Set cell values as {(col, row): intensity}.

        ``max_value`` is used for normalization; if omitted it is derived
        from ``values``.
        """
        self._values = values
        self._max_value = (
            max_value
            if max_value is not None
            else (max(values.values()) if values else 0)
        )

    def _default_color_for(self, value: int, max_value: int) -> tuple[int, int, int]:
        """Log-scale color mapping (suitable for skewed count data)."""
        if value == 0:
            return self._colors[0]
        if max_value <= 1:
            return self._colors[1]
        ratio = math.log(value) / math.log(max_value)
        max_level = len(self._colors) - 1
        level = max(1, min(max_level, int(ratio * (max_level - 1)) + 1))
        return self._colors[level]

    def _render_surface(self, surface) -> None:
        cell_w = wcswidth(self._cell_char)
        max_col = surface.width
        max_row = surface.height
        for (c, r), value in self._values.items():
            if r < 0 or r >= self._rows or c < 0 or c >= self._cols:
                continue
            col = self._margin_left + c * cell_w
            row = self._margin_top + r
            if col >= max_col or row >= max_row:
                continue
            color = self._color_fn(value, self._max_value)
            ch = self._cell_char if value > 0 else self._empty_char
            surface.draw_text_rgb(row, col, ch, fg=color, bg=self._bg)


class StepLineChart(Component):
    """Multi-series stepped line chart with Y/X axes and legend."""

    def __init__(
        self,
        x: int = 1,
        y: int = 1,
        size: Optional[tuple[int, int]] = None,
        *,
        plot_w: int = 55,
        plot_h: int = 7,
        colors: list[tuple[int, int, int]],
        bg: tuple[int, int, int],
        title: str = "",
        title_fg: tuple[int, int, int] = palette.DEFAULT_FG,
        label_fg: tuple[int, int, int] = palette.DEFAULT_FG_DIM,
        axis_fg: tuple[int, int, int] = palette.DEFAULT_FG_DIM,
        y_axis_label_w: int = 5,
        padding_left: int = 2,
    ) -> None:
        super().__init__(x, y, size)
        self._plot_w = plot_w
        self._plot_h = plot_h
        self._colors = colors
        self._bg = bg
        self._title = title
        self._title_fg = title_fg
        self._label_fg = label_fg
        self._axis_fg = axis_fg
        self._y_axis_label_w = y_axis_label_w
        self._padding_left = padding_left
        self._series: dict[str, list[int]] = {}
        self._x_labels: list[tuple[int, str]] = []
        self._overall_max = 0

    @property
    def min_size(self) -> tuple[int, int]:
        """Return (min_width, min_height) needed to render the chart."""
        title_h = 1 if self._title else 0
        total_h = title_h + self._plot_h + 2 + 2  # x_axis(2) + legend(2)
        min_w = self._padding_left + self._y_axis_label_w + 1 + self._plot_w
        return (min_w, total_h)

    def set_series(
        self,
        series: dict[str, list[int]],
        x_labels: Optional[list[tuple[int, str]]] = None,
    ) -> None:
        """Set data series and optional X-axis labels."""
        self._series = series
        self._x_labels = x_labels or []
        self._overall_max = 0
        for s in self._series.values():
            self._overall_max = max(self._overall_max, max(s) if s else 0)

    def _render_surface(self, surface) -> None:
        plot_w = self._plot_w
        plot_h = self._plot_h
        title_h = 1 if self._title else 0
        x_axis_h = 2
        legend_h = 2
        total_h = title_h + plot_h + x_axis_h + legend_h

        min_width = self._padding_left + self._y_axis_label_w + 1 + plot_w
        if surface.height < total_h or surface.width < min_width:
            return

        surf_w = surface.width
        surf_h = surface.height
        overall_max = self._overall_max
        if overall_max == 0:
            return

        # Title
        if self._title:
            surface.draw_text_rgb(
                0,
                self._padding_left,
                self._title,
                fg=self._title_fg,
                bg=self._bg,
                style_flags=palette.STYLE_BOLD,
            )

        chart_top = title_h
        chart_bottom = chart_top + plot_h - 1
        y_axis_col = self._padding_left + self._y_axis_label_w

        # Y-axis labels (one per horizontal grid line, top to bottom)
        for i in range(plot_h):
            row = chart_top + i
            value = int(round(overall_max * (plot_h - 1 - i) / (plot_h - 1)))
            label = str(value)
            pad = max(0, self._y_axis_label_w - len(label))
            surface.draw_text_rgb(
                row,
                self._padding_left + pad,
                label,
                fg=self._label_fg,
                bg=self._bg,
            )

        # Y-axis line with ticks: ┤ for ticks, ┼ for origin
        for r in range(chart_top, chart_bottom + 1):
            ch = _BOX_CROSS if r == chart_bottom else _BOX_TICK
            surface.draw_text_rgb(r, y_axis_col, ch, fg=self._axis_fg, bg=self._bg)

        # X-axis line
        x_axis_row = chart_bottom
        x_axis_end = y_axis_col + 1 + plot_w
        if x_axis_end <= surf_w:
            surface.draw_text_rgb(
                x_axis_row,
                y_axis_col + 1,
                _BOX_H * plot_w,
                fg=self._axis_fg,
                bg=self._bg,
            )

        # X-axis labels
        for col_idx, label in self._x_labels:
            col = y_axis_col + 1 + col_idx
            if col + len(label) <= surf_w and x_axis_row + 1 < surf_h:
                surface.draw_text_rgb(
                    x_axis_row + 1,
                    col,
                    label,
                    fg=self._label_fg,
                    bg=self._bg,
                )

        plot_start_col = y_axis_col + 1
        num_colors = len(self._colors)

        # Draw lines (uniformly mapped to plot_w columns)
        for aidx, (name, series) in enumerate(self._series.items()):
            color = self._colors[aidx % num_colors]
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
                col = plot_start_col + c
                if col >= surf_w or row < 0 or row >= surf_h:
                    continue
                surface.draw_text_rgb(row, col, _BOX_H, fg=color, bg=self._bg)

            # Second pass: rounded step connections at column boundaries
            for c in range(plot_w - 1):
                row = mapped_rows[c]
                next_row = mapped_rows[c + 1]
                col = plot_start_col + c + 1
                if col >= surf_w:
                    continue
                if next_row < row:  # ascending (next point is higher)
                    if row < surf_h:
                        surface.draw_text_rgb(
                            row, col, _BOX_CORNER_BR, fg=color, bg=self._bg
                        )
                    for r in range(next_row + 1, row):
                        if 0 <= r < surf_h and col < surf_w:
                            surface.draw_text_rgb(r, col, _BOX_V, fg=color, bg=self._bg)
                    if 0 <= next_row < surf_h:
                        surface.draw_text_rgb(
                            next_row, col, _BOX_CORNER_TL, fg=color, bg=self._bg
                        )
                elif next_row > row:  # descending (next point is lower)
                    if row < surf_h:
                        surface.draw_text_rgb(
                            row, col, _BOX_CORNER_TR, fg=color, bg=self._bg
                        )
                    for r in range(row + 1, next_row):
                        if 0 <= r < surf_h and col < surf_w:
                            surface.draw_text_rgb(r, col, _BOX_V, fg=color, bg=self._bg)
                    if 0 <= next_row < surf_h:
                        surface.draw_text_rgb(
                            next_row, col, _BOX_CORNER_BL, fg=color, bg=self._bg
                        )

        # Legend
        legend_row = x_axis_row + 2
        if legend_row >= surf_h:
            return
        x = self._padding_left
        for aidx, (name, series) in enumerate(self._series.items()):
            color = self._colors[aidx % num_colors]
            entry_width = 2 + len(name) + 3
            if x + entry_width > surf_w:
                break
            surface.draw_text_rgb(legend_row, x, "*", fg=color, bg=self._bg)
            x += 2
            surface.draw_text_rgb(legend_row, x, name, fg=self._label_fg, bg=self._bg)
            x += len(name) + 3
