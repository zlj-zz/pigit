"""
Module: tests/termui/test_graph_widgets.py
Description: Tests for the grid and line-chart widgets and the calendar helpers.
Author: Zev
Date: 2026-08-20
"""

from __future__ import annotations

import datetime

from pigit.termui.primitives import (
    build_contribution_calendar,
    calendar_day_values,
)
from pigit.termui import Component
from pigit.termui.surface import Surface
from pigit.termui.widgets.graph import StepLineChart


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


def test_line_chart_legend_keeps_its_row_on_a_taller_surface():
    """``legend_row`` is the chart's own, not the bottom of whatever box it got."""
    chart = StepLineChart(plot_w=10, plot_h=3, colors=[(1, 2, 3)], bg=None, title="T")
    chart.set_series({"a": [1, 2, 3], "b": [3, 2, 1]})
    surface = Surface(40, chart.total_h + 10)
    chart.paint(surface)
    rows = ["".join(cell.char for cell in row) for row in surface._rows]

    assert "*─ a" in rows[chart.legend_row]
    assert not any(row.strip() for row in rows[chart.legend_row + 1 :])


def test_components_have_no_natural_size_unless_they_need_one():
    """The protocol's default is "take what you are given"."""

    class Plain(Component):
        def paint(self, surface):  # pragma: no cover - never painted here
            pass

    assert Plain().natural_size is None


def test_line_chart_natural_size_fits_its_rightmost_label():
    """``min_size`` stops at the plot; past it the x labels get dropped.

    A label that does not fit is skipped silently, so the width the chart
    needs is where the rightmost one ends — exactly one column less would
    lose it.
    """
    chart = StepLineChart(plot_w=55, plot_h=7, colors=[(1, 2, 3)], bg=None, title="T")
    labels = [(0, "Sep 06"), (27, "Sep 21"), (54, "Oct 06")]
    chart.set_series({"a": [i % 5 for i in range(30)]}, x_labels=labels)

    width, height = chart.natural_size
    assert height == chart.total_h
    assert width > chart.min_size[0], "plot width alone would drop 'Oct 06'"

    def labels_at(w: int) -> str:
        surface = Surface(w, height)
        chart.paint(surface)
        return "".join(cell.char for cell in surface._rows[8])

    row = labels_at(width)
    assert all(text in row for _, text in labels)
    assert "Oct 06" not in labels_at(width - 1)


def test_line_chart_natural_size_falls_back_to_the_plot_width():
    """With no labels there is nothing past the plot to make room for."""
    chart = StepLineChart(plot_w=20, plot_h=3, colors=[(1, 2, 3)], bg=None)
    chart.set_series({"a": [1, 2, 3]})
    assert chart.natural_size == chart.min_size
