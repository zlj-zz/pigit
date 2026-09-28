# -*- coding: utf-8 -*-
"""
Module: tests/termui/test_wcwidth_table.py
Description: Display-width helpers, especially left-slicing by columns.
Author: Zev
Date: 2026-09-28
"""

from __future__ import annotations

import pytest

from pigit.termui.wcwidth_table import slice_left_by_width, wcswidth

CASES = [
    ("中文abc", 2, "文abc"),
    ("中文abc", 4, "abc"),
    ("中文", 0, "中文"),
    ("中文", 3, " "),  # cut inside 文: one column survives, drawn blank
    ("中", 1, " "),
    ("a中", 2, " "),
    ("abc", 5, ""),
    ("abc", 3, ""),
    ("", 3, ""),
]


@pytest.mark.parametrize("text, skip, expected", CASES)
def test_slice_left_by_width(text, skip, expected):
    assert slice_left_by_width(text, skip) == expected


@pytest.mark.parametrize("text, skip, _expected", CASES)
def test_slice_preserves_the_width_invariant(text, skip, _expected):
    """Callers lay out what follows by column, so the result must be exactly
    ``width - skip`` columns wide — never less, or the rest of the line shifts
    left by the difference."""
    result = slice_left_by_width(text, skip)
    assert wcswidth(result) == max(0, wcswidth(text) - skip)


def test_slice_keeps_a_combining_mark_with_its_base():
    assert slice_left_by_width("éx", 1) == "́x"


def test_negative_skip_returns_text_unchanged():
    assert slice_left_by_width("中文", -1) == "中文"
