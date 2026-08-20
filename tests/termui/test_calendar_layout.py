"""
Module: tests/termui/test_calendar_layout.py
Description: Tests for contribution heatmap week-grid layout helpers.
Author: Zev
Date: 2026-08-20
"""

from __future__ import annotations

import datetime

from pigit.termui.primitives import (
    build_contribution_calendar,
    calendar_day_values,
)
from pigit.termui.surface import Surface
from pigit.app_contribution_graph import ContributionGraph


def test_contribution_graph_excludes_future_cells():
    """Days after today in the final partial week render as blank, not '·'."""
    graph = ContributionGraph(size=(100, 24))
    graph.set_commits([])
    first_monday = graph._first_monday
    today = datetime.date.today()
    graph._render_surface(Surface(100, 24))
    for week, day in graph._heatmap._values:
        date = first_monday + datetime.timedelta(weeks=week, days=day)
        assert date <= today


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
