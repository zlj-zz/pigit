"""
Module: pigit/termui/primitives/calendar_layout.py
Description: Week-grid layout helpers for contribution heatmaps.
Author: Zev
Date: 2026-08-20
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass


@dataclass(frozen=True)
class ContributionCalendar:
    """Aligned week grid spanning a contribution heatmap window.

    Attributes:
        today: Last visible calendar day (inclusive).
        first_monday: Monday on or before the window start.
        num_weeks: Number of week columns from ``first_monday`` through ``today``.
    """

    today: datetime.date
    first_monday: datetime.date
    num_weeks: int


def build_contribution_calendar(
    today: datetime.date,
    *,
    days_back: int = 365,
) -> ContributionCalendar:
    """Align ``today - days_back`` to Monday; compute week count through today.

    Args:
        today: Reference date for the heatmap's right edge.
        days_back: Number of days before ``today`` to include.

    Returns:
        ContributionCalendar with aligned Monday start and week count.
    """
    start = today - datetime.timedelta(days=days_back)
    first_monday = start - datetime.timedelta(days=start.weekday())
    days = (today - first_monday).days + 1
    num_weeks = (days + 6) // 7
    return ContributionCalendar(
        today=today,
        first_monday=first_monday,
        num_weeks=num_weeks,
    )


def calendar_day_values(
    day_counts: dict[datetime.date, int],
    calendar: ContributionCalendar,
) -> dict[tuple[int, int], int]:
    """Map ``(week, weekday0=Mon)`` → count; skip dates after ``calendar.today``.

    Args:
        day_counts: Commit counts keyed by calendar date.
        calendar: Precomputed week grid bounds.

    Returns:
        Heatmap cell values keyed by ``(week_index, weekday_index)``.
    """
    values: dict[tuple[int, int], int] = {}
    for week in range(calendar.num_weeks):
        for day in range(7):
            date = calendar.first_monday + datetime.timedelta(weeks=week, days=day)
            if date > calendar.today:
                continue
            values[(week, day)] = day_counts.get(date, 0)
    return values
