# -*- coding: utf-8 -*-
"""Tests for pigit.termui.surface RGB and FlatCell features."""

from __future__ import annotations

import pytest

from pigit.termui._surface import FlatCell, Surface


class TestFlatCell:
    def test_default_cell(self):
        c = FlatCell()
        assert c.char == " "
        assert c.fg == (220, 220, 230)
        assert c.bg == (18, 18, 22)
        assert c.bold is False
        assert c.ansi_style is None
        assert c.style == ""  # backward compat

    def test_legacy_style_kwarg(self):
        c = FlatCell("X", style="\033[31m")
        assert c.char == "X"
        assert c.ansi_style == "\033[31m"
        assert c.style == "\033[31m"

    def test_ansi_style_kwarg(self):
        c = FlatCell("X", ansi_style="\033[31m")
        assert c.ansi_style == "\033[31m"
        assert c.style == "\033[31m"

    def test_rgb_values(self):
        c = FlatCell("A", fg=(255, 0, 0), bg=(0, 255, 0), bold=True)
        assert c.fg == (255, 0, 0)
        assert c.bg == (0, 255, 0)
        assert c.bold is True

    def test_equality(self):
        a = FlatCell("x", fg=(255, 0, 0))
        b = FlatCell("x", fg=(255, 0, 0))
        c = FlatCell("x", fg=(0, 255, 0))
        assert a == b
        assert a != c
        assert hash(a) == hash(b)

    def test_cell_alias(self):
        from pigit.termui._surface import Cell

        c = Cell("X", style="\033[31m")
        assert isinstance(c, FlatCell)
        assert c.ansi_style == "\033[31m"


class TestSurfaceRGB:
    def test_draw_text_rgb_basic(self):
        s = Surface(5, 1)
        s.draw_text_rgb(0, 0, "hello", fg=(255, 0, 0), bg=(0, 0, 0))
        row = s.rows()[0]
        assert row[0].char == "h"
        assert row[0].fg == (255, 0, 0)
        assert row[0].bg == (0, 0, 0)
        assert row[0].ansi_style is None

    def test_draw_text_rgb_clipping(self):
        s = Surface(3, 1)
        s.draw_text_rgb(0, 1, "hello", fg=(255, 0, 0))
        row = s.rows()[0]
        assert row[0].char == " "
        assert row[1].char == "h"
        assert row[2].char == "e"

    def test_draw_text_rgb_out_of_bounds(self):
        s = Surface(3, 1)
        s.draw_text_rgb(0, 3, "hi", fg=(255, 0, 0))
        # No cells should be written
        assert all(c.char == " " for c in s.rows()[0])

    def test_fill_rect_rgb(self):
        s = Surface(4, 3)
        s.fill_rect_rgb(1, 1, 2, 2, bg=(0, 0, 255))
        assert s.rows()[0][0].bg == (18, 18, 22)  # unchanged
        assert s.rows()[1][1].bg == (0, 0, 255)
        assert s.rows()[1][2].bg == (0, 0, 255)
        assert s.rows()[2][1].bg == (0, 0, 255)
        assert s.rows()[2][2].bg == (0, 0, 255)

    def test_draw_row_rgb(self):
        s = Surface(5, 1)
        s.draw_row_rgb(0, "hi", fg=(255, 255, 255), bg=(0, 0, 0))
        row = s.rows()[0]
        assert row[0].char == "h"
        assert row[0].fg == (255, 255, 255)
        assert row[4].char == " "  # padded

    def test_draw_row_rgb_center(self):
        s = Surface(6, 1)
        s.draw_row_rgb(0, "hi", fg=(255, 0, 0), align="center")
        line = s.lines()[0]
        assert line == "  hi  "

    def test_fill_row_bg(self):
        s = Surface(5, 1)
        s.draw_text(0, 0, "hello")
        s.fill_row_bg(0, (100, 100, 100))
        row = s.rows()[0]
        assert row[0].char == "h"
        assert row[0].bg == (100, 100, 100)
        assert row[4].char == "o"
        assert row[4].bg == (100, 100, 100)

    def test_fill_row_bg_preserves_fg(self):
        s = Surface(3, 1)
        s.draw_text_rgb(0, 0, "A", fg=(255, 0, 0))
        s.fill_row_bg(0, (0, 0, 255))
        row = s.rows()[0]
        assert row[0].fg == (255, 0, 0)
        assert row[0].bg == (0, 0, 255)

    def test_subsurface_with_margin(self):
        s = Surface(10, 10)
        sub = s.subsurface_with_margin(0, 0, 10, 10, margin_top=1, margin_bottom=1, margin_left=2, margin_right=2)
        assert sub.width == 6
        assert sub.height == 8
        sub.draw_text(0, 0, "x")
        assert s.lines()[1][2] == "x"

    def test_subsurface_rgb_proxy(self):
        s = Surface(5, 3)
        sub = s.subsurface(1, 1, 3, 2)
        sub.draw_text_rgb(0, 0, "AB", fg=(255, 0, 0))
        assert s.rows()[1][1].fg == (255, 0, 0)
        assert s.rows()[1][2].fg == (255, 0, 0)

    def test_mixed_legacy_and_rgb_cells(self):
        s = Surface(4, 1)
        s.draw_text(0, 0, "\033[31mAB")
        s.draw_text_rgb(0, 2, "CD", fg=(0, 255, 0))
        row = s.rows()[0]
        assert row[0].ansi_style == "\033[31m"
        assert row[2].fg == (0, 255, 0)
        assert row[2].ansi_style is None

    def test_lines_returns_plain_strings(self):
        s = Surface(3, 1)
        s.draw_text_rgb(0, 0, "abc", fg=(255, 0, 0))
        assert s.lines()[0] == "abc"


class TestSurfaceRGBEdgeCases:
    def test_draw_text_rgb_negative_row(self):
        s = Surface(3, 1)
        s.draw_text_rgb(-1, 0, "hi", fg=(255, 0, 0))
        assert all(c.char == " " for c in s.rows()[0])

    def test_fill_rect_rgb_out_of_bounds(self):
        s = Surface(3, 3)
        s.fill_rect_rgb(5, 5, 2, 2, bg=(255, 0, 0))
        # Should be a no-op
        for row in s.rows():
            for cell in row:
                assert cell.bg == (18, 18, 22)

    def test_fill_row_bg_out_of_bounds(self):
        s = Surface(3, 1)
        s.fill_row_bg(-1, (255, 0, 0))
        s.fill_row_bg(5, (255, 0, 0))
        # No crash, no changes
        assert all(c.bg == (18, 18, 22) for c in s.rows()[0])


class TestSurfaceRGBWideChars:
    """Regression tests for wide-character (CJK) rendering overflow."""

    def test_draw_text_rgb_wide_char_occupies_two_cells(self):
        s = Surface(5, 1)
        s.draw_text_rgb(0, 0, "中", fg=(255, 0, 0))
        row = s.rows()[0]
        assert row[0].char == "中"
        assert row[1].char == ""  # spacer cell
        assert row[2].char == " "

    def test_draw_text_rgb_wide_char_with_ascii(self):
        s = Surface(6, 1)
        s.draw_text_rgb(0, 0, "A中B", fg=(255, 0, 0))
        row = s.rows()[0]
        assert row[0].char == "A"
        assert row[1].char == "中"
        assert row[2].char == ""  # spacer for 中
        assert row[3].char == "B"
        assert row[4].char == " "

    def test_draw_text_rgb_wide_char_clipping_at_boundary(self):
        """Wide char starting at last column should be skipped."""
        s = Surface(3, 1)
        s.draw_text_rgb(0, 2, "中", fg=(255, 0, 0))
        row = s.rows()[0]
        # col 2 is last valid index; wide char needs cols 2+3 which is out of bounds
        assert row[2].char == " "

    def test_draw_text_rgb_wide_char_does_not_overflow(self):
        """Regression: draw_text_rgb must not write beyond surface width."""
        s = Surface(4, 1)
        s.draw_text_rgb(0, 1, "中BC", fg=(255, 0, 0))
        row = s.rows()[0]
        assert row[0].char == " "
        assert row[1].char == "中"
        assert row[2].char == ""  # spacer
        assert row[3].char == "B"  # C is clipped

    def test_draw_row_rgb_wide_char_no_overflow(self):
        s = Surface(5, 1)
        s.draw_row_rgb(0, "中文", fg=(255, 0, 0))
        row = s.rows()[0]
        assert row[0].char == "中"
        assert row[1].char == ""
        assert row[2].char == "文"
        assert row[3].char == ""
        assert row[4].char == " "
