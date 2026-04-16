# -*- coding: utf-8 -*-
"""Tests for pigit.termui.picker_layout and tty_io truncation helpers."""

from __future__ import annotations

from pigit.termui.picker_layout import truncate_visual
from pigit.termui.tty_io import truncate_line


class TestTruncateVisual:
    def test_fits_within_max_cols(self):
        assert truncate_visual("hello", 10) == "hello"

    def test_truncates_ascii(self):
        assert truncate_visual("hello world", 8) == "hello w…"

    def test_max_cols_one(self):
        assert truncate_visual("hello", 1) == "h"

    def test_zero_or_negative_returns_empty(self):
        assert truncate_visual("hello", 0) == ""
        assert truncate_visual("hello", -1) == ""

    def test_truncates_cjk_by_display_width(self):
        assert truncate_visual("中文测试", 5) == "中文…"


class TestTruncateLine:
    def test_fits_within_max_cols(self):
        assert truncate_line("hello world", 20) == "hello world"

    def test_collapses_whitespace(self):
        assert truncate_line("hello\n\tworld", 20) == "hello world"

    def test_truncates_ascii(self):
        assert truncate_line("hello world", 8) == "hello w…"

    def test_max_cols_one(self):
        assert truncate_line("hello", 1) == "h"

    def test_zero_or_negative_returns_empty(self):
        assert truncate_line("hello", 0) == ""

    def test_truncates_cjk_by_display_width(self):
        assert truncate_line("中文测试", 5) == "中文…"
