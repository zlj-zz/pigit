"""
Module: tests/termui/test_gutter.py
Description: Tests for diff line-number gutter formatting.
Author: Zev
Date: 2026-08-20
"""

from __future__ import annotations

from pigit.termui.primitives import format_line_number


def test_format_line_number_right_justifies_int():
    assert format_line_number(42, 4) == "  42"
    assert format_line_number(1, 4) == "   1"


def test_format_line_number_blank_string():
    assert format_line_number("", 4) == "    "
    assert len(format_line_number("", 4)) == 4


def test_format_line_number_truncates_overflow():
    """Numbers wider than the gutter keep their rightmost digits instead of
    overflowing into the +/- prefix column."""
    assert format_line_number(10000, 4) == "0000"
    assert format_line_number(10001, 4) == "0001"
    assert len(format_line_number(123456, 4)) == 4
