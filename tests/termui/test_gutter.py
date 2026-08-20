"""
Module: tests/termui/test_gutter.py
Description: Tests for diff line-number gutter formatting.
Author: Zev
Date: 2026-08-20
"""

from __future__ import annotations

from pigit.termui.widgets.gutter import format_line_number


def test_format_line_number_right_justifies_int():
    assert format_line_number(42, 4) == "  42"
    assert format_line_number(1, 4) == "   1"


def test_format_line_number_blank_string():
    assert format_line_number("", 4) == "    "
    assert len(format_line_number("", 4)) == 4
