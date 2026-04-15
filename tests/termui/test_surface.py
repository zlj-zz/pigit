# -*- coding: utf-8 -*-
"""
Tests for pigit.termui.surface.
"""

from __future__ import annotations

from pigit.termui.surface import Cell, Surface


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
    def test_draw_text_clipping(self):
        s = Surface(10, 3)
        s.draw_text(1, 8, "hello")
        assert s.lines()[1] == "        he"

    def test_draw_row_truncate(self):
        s = Surface(5, 1)
        s.draw_row(0, "hello world")
        assert s.lines()[0] == "hell…"

    def test_draw_row_center(self):
        s = Surface(10, 1)
        s.draw_row(0, "hi", align="center")
        assert s.lines()[0] == "    hi    "

    def test_draw_box(self):
        s = Surface(6, 4)
        s.draw_box(0, 0, 6, 4, title="T")
        lines = s.lines()
        assert lines[0].startswith("┌")
        assert lines[0].endswith("┐")

    def test_fill_rect(self):
        s = Surface(5, 3)
        s.fill_rect(1, 1, 3, 2, "#")
        assert s.lines()[1] == " ### "
        assert s.lines()[2] == " ### "

    def test_clear_resets_all_cells(self):
        s = Surface(4, 2)
        s.draw_text(0, 0, "ABCD")
        s.draw_text(1, 0, "EFGH")
        s.clear()
        assert s.lines() == ["    ", "    "]

    def test_lines_returns_strings(self):
        s = Surface(3, 2)
        s.draw_text(0, 0, "abc")
        s.draw_text(1, 0, "de")
        assert s.lines() == ["abc", "de "]

    def test_draw_text_out_of_bounds_is_noop(self):
        s = Surface(3, 2)
        s.draw_text(-1, 0, "abc")
        s.draw_text(2, 0, "abc")
        s.draw_text(0, 3, "abc")
        assert s.lines() == ["   ", "   "]

    def test_draw_text_partially_visible_from_negative_col(self):
        s = Surface(3, 1)
        s.draw_text(0, -1, "abc")
        assert s.lines()[0] == "bc "
