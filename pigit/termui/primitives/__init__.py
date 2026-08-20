# -*- coding: utf-8 -*-
"""
Package: pigit.termui.primitives
Description: Stable text/layout/diff helpers (not part of the root façade).
Author: Zev
Date: 2026-08-20
"""

from __future__ import annotations

from .ansi import parse_ansi_line
from .calendar_layout import (
    ContributionCalendar,
    build_contribution_calendar,
    calendar_day_values,
)
from .frame import BoxFrame
from .gutter import format_line_number
from .text import plain
from .word_diff import merge_ranges, tokenize_with_positions

__all__ = [
    "plain",
    "BoxFrame",
    "parse_ansi_line",
    "tokenize_with_positions",
    "merge_ranges",
    "format_line_number",
    "ContributionCalendar",
    "build_contribution_calendar",
    "calendar_day_values",
]
