# -*- coding: utf-8 -*-
"""
Module: tests/termui/test_primitives_api.py
Description: Contract for pigit.termui.primitives façade (filled in Phase 1).
Author: Zev
Date: 2026-08-20
"""

from __future__ import annotations

PRIMITIVES_EXPORTS = (
    "plain",
    "BoxFrame",
    "parse_ansi_line",
    "tokenize_with_positions",
    "merge_ranges",
    "format_line_number",
    "ContributionCalendar",
    "build_contribution_calendar",
    "calendar_day_values",
)


def test_primitives_package_exports():
    from pigit.termui import primitives

    for name in PRIMITIVES_EXPORTS:
        assert hasattr(primitives, name)
        assert name in primitives.__all__
