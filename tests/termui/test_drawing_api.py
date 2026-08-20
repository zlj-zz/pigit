# -*- coding: utf-8 -*-
"""
Module: tests/termui/test_drawing_api.py
Description: Contract for pigit.termui.drawing façade (filled in Phase 1).
Author: Zev
Date: 2026-08-20
"""

from __future__ import annotations

import pytest

DRAWING_EXPORTS = (
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


@pytest.mark.skip(reason="drawing package lands in Phase 1")
def test_drawing_package_exports():
    from pigit.termui import drawing

    for name in DRAWING_EXPORTS:
        assert hasattr(drawing, name)
        assert name in drawing.__all__
