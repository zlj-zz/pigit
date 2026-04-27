# -*- coding: utf-8 -*-
"""
Tests for pigit.termui.surface.
"""

from __future__ import annotations

import pytest

from pigit.termui._surface import Cell, FlatCell, Surface
from pigit.termui.palette import DEFAULT_BG, DEFAULT_FG


class TestCell:
    def test_default_cell_is_blank(self):
        c = Cell()
        assert c.char == " "
        assert c.style == ""

    def test_cell_with_values(self):
        c = Cell(char="X", style="\033[31m")
        assert c.char == "X"
        assert c.style == "\033[31m"


class TestSurface:
    def test_draw_text_rgb_clipping(self):
        s = Surface(10, 3)
        s.draw_text_rgb(1, 8, "hello", fg=DEFAULT_FG, bg=DEFAULT_BG)
        assert s.lines()[1] == "        he"

    def test_draw_box_rgb(self):
        s = Surface(6, 4)
        s.draw_box_rgb(0, 0, 6, 4, fg=DEFAULT_FG, bg=DEFAULT_BG, title="T")
        lines = s.lines()
        assert lines[0].startswith("┌")
        assert lines[0].endswith("┐")

    def test_clear_resets_all_cells(self):
        s = Surface(4, 2)
        s.draw_text_rgb(0, 0, "ABCD", fg=DEFAULT_FG, bg=DEFAULT_BG)
        s.draw_text_rgb(1, 0, "EFGH", fg=DEFAULT_FG, bg=DEFAULT_BG)
        s.clear()
        assert s.lines() == ["    ", "    "]

    def test_lines_returns_strings(self):
        s = Surface(3, 2)
        s.draw_text_rgb(0, 0, "abc", fg=DEFAULT_FG, bg=DEFAULT_BG)
        s.draw_text_rgb(1, 0, "de", fg=DEFAULT_FG, bg=DEFAULT_BG)
        assert s.lines() == ["abc", "de "]

    def test_draw_text_rgb_out_of_bounds_is_noop(self):
        s = Surface(3, 2)
        s.draw_text_rgb(-1, 0, "abc", fg=DEFAULT_FG, bg=DEFAULT_BG)
        s.draw_text_rgb(2, 0, "abc", fg=DEFAULT_FG, bg=DEFAULT_BG)
        s.draw_text_rgb(0, 3, "abc", fg=DEFAULT_FG, bg=DEFAULT_BG)
        assert s.lines() == ["   ", "   "]

    def test_draw_text_rgb_basic(self):
        s = Surface(10, 3)
        s.draw_text_rgb(1, 2, "hello", fg=DEFAULT_FG, bg=DEFAULT_BG)
        assert s.lines()[1] == "  hello   "

    def test_draw_box_rgb_with_title(self):
        s = Surface(10, 4)
        s.draw_box_rgb(0, 0, 10, 4, fg=DEFAULT_FG, bg=DEFAULT_BG, title="Test")
        lines = s.lines()
        assert "Test" in lines[0]
        assert lines[0].startswith("┌")
        assert lines[-1].startswith("└")

    def test_draw_text_rgb_partially_visible_from_negative_col(self):
        s = Surface(3, 1)
        s.draw_text_rgb(0, -1, "abc", fg=DEFAULT_FG, bg=DEFAULT_BG)
        assert s.lines()[0] == "bc "


class TestSurfaceCJK:
    def test_wide_char_occupies_two_cells_with_spacer(self):
        s = Surface(4, 1)
        s.draw_text_rgb(0, 0, "中a", fg=DEFAULT_FG, bg=DEFAULT_BG)
        row = s.rows()[0]
        assert row[0].char == "中"
        assert row[1].char == ""
        assert row[2].char == "a"
        assert row[3].char == " "

    def test_wide_char_clipped_at_right_edge(self):
        s = Surface(3, 1)
        s.draw_text_rgb(0, 2, "中", fg=DEFAULT_FG, bg=DEFAULT_BG)
        row = s.rows()[0]
        assert row[2].char == " "  # not enough room for width-2 char

    def test_draw_box_rgb_title_centers_cjk_correctly(self):
        s = Surface(10, 3)
        s.draw_box_rgb(0, 0, 10, 3, fg=DEFAULT_FG, bg=DEFAULT_BG, title="中")
        lines = s.lines()
        assert "中" in lines[0]


class TestSubsurface:
    def test_translation(self):
        parent = Surface(5, 5)
        sub = parent.subsurface(1, 1, 3, 3)
        sub.draw_text_rgb(0, 0, "x", fg=DEFAULT_FG, bg=DEFAULT_BG)
        assert parent.lines()[1][1] == "x"

    def test_clipping_negative_row(self):
        parent = Surface(5, 5)
        sub = parent.subsurface(1, 1, 3, 3)
        sub.draw_text_rgb(-1, 0, "x", fg=DEFAULT_FG, bg=DEFAULT_BG)
        # Should be a no-op
        assert parent.lines()[0] == "     "

    def test_clipping_col_beyond_width(self):
        parent = Surface(5, 5)
        sub = parent.subsurface(1, 1, 3, 3)
        sub.draw_text_rgb(0, 3, "x", fg=DEFAULT_FG, bg=DEFAULT_BG)
        # col >= width is a no-op
        assert parent.lines()[1] == "     "

    def test_nested_subsurface(self):
        parent = Surface(6, 6)
        sub1 = parent.subsurface(1, 1, 4, 4)
        sub2 = sub1.subsurface(1, 1, 2, 2)
        sub2.draw_text_rgb(0, 0, "z", fg=DEFAULT_FG, bg=DEFAULT_BG)
        assert parent.lines()[2][2] == "z"

    def test_draw_box_rgb_clipped_by_subsurface_bounds(self):
        parent = Surface(6, 6)
        sub = parent.subsurface(1, 1, 3, 3)
        sub.draw_box_rgb(0, 0, 5, 5, fg=DEFAULT_FG, bg=DEFAULT_BG)
        # Only 3x3 area should be affected inside the subsurface
        lines = parent.lines()
        assert lines[1][1] == "┌"
        assert lines[1][3] == "┐"
        assert lines[3][1] == "└"
        assert lines[3][3] == "┘"


class TestSurfaceEdgeCases:
    def test_draw_box_rgb_too_small_is_noop(self):
        s = Surface(3, 3)
        s.draw_box_rgb(0, 0, 1, 3, fg=DEFAULT_FG, bg=DEFAULT_BG)
        assert s.lines() == ["   ", "   ", "   "]
        s2 = Surface(3, 3)
        s2.draw_box_rgb(0, 0, 3, 1, fg=DEFAULT_FG, bg=DEFAULT_BG)
        assert s2.lines() == ["   ", "   ", "   "]


class TestSubsurfaceEdgeCases:
    def test_draw_box_rgb_clipped_to_zero_is_noop(self):
        parent = Surface(5, 5)
        sub = parent.subsurface(1, 1, 3, 3)
        sub.draw_box_rgb(0, 2, 5, 5, fg=DEFAULT_FG, bg=DEFAULT_BG)  # col=2 >= width=3 -> clipped None
        assert parent.lines()[1] == "     "


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

    def test_subsurface_with_margin(self):
        s = Surface(10, 10)
        sub = s.subsurface_with_margin(
            0, 0, 10, 10, margin_top=1, margin_bottom=1, margin_left=2, margin_right=2
        )
        assert sub.width == 6
        assert sub.height == 8
        sub.draw_text_rgb(0, 0, "x", fg=DEFAULT_FG, bg=DEFAULT_BG)
        assert s.lines()[1][2] == "x"

    def test_subsurface_rgb_proxy(self):
        s = Surface(5, 3)
        sub = s.subsurface(1, 1, 3, 2)
        sub.draw_text_rgb(0, 0, "AB", fg=(255, 0, 0))
        assert s.rows()[1][1].fg == (255, 0, 0)
        assert s.rows()[1][2].fg == (255, 0, 0)

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

