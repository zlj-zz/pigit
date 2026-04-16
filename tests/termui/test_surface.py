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

    def test_draw_text_basic(self):
        s = Surface(10, 3)
        s.draw_text(1, 2, "hello")
        assert s.lines()[1] == "  hello   "

    def test_draw_box_with_title(self):
        s = Surface(10, 4)
        s.draw_box(0, 0, 10, 4, title="Test")
        lines = s.lines()
        assert "Test" in lines[0]
        assert lines[0].startswith("┌")
        assert lines[-1].startswith("└")

    def test_draw_text_partially_visible_from_negative_col(self):
        s = Surface(3, 1)
        s.draw_text(0, -1, "abc")
        assert s.lines()[0] == "bc "


class TestSurfaceCJK:
    def test_wide_char_occupies_two_cells_with_spacer(self):
        s = Surface(4, 1)
        s.draw_text(0, 0, "中a")
        row = s.rows()[0]
        assert row[0].char == "中"
        assert row[1].char == ""
        assert row[2].char == "a"
        assert row[3].char == " "

    def test_wide_char_clipped_at_right_edge(self):
        s = Surface(3, 1)
        s.draw_text(0, 2, "中")
        row = s.rows()[0]
        assert row[2].char == " "  # not enough room for width-2 char

    def test_draw_row_truncates_cjk_by_display_width(self):
        s = Surface(5, 1)
        s.draw_row(0, "中文test")
        line = s.lines()[0]
        assert "…" in line
        # line fits within the 5-column surface (CJK chars are 2 cols each)
        assert line == "中文…"

    def test_draw_box_title_centers_cjk_correctly(self):
        s = Surface(10, 3)
        s.draw_box(0, 0, 10, 3, title="中")
        lines = s.lines()
        assert "中" in lines[0]


class TestSubsurface:
    def test_translation(self):
        parent = Surface(5, 5)
        sub = parent.subsurface(1, 1, 3, 3)
        sub.draw_text(0, 0, "x")
        assert parent.lines()[1][1] == "x"

    def test_clipping_negative_row(self):
        parent = Surface(5, 5)
        sub = parent.subsurface(1, 1, 3, 3)
        sub.draw_text(-1, 0, "x")
        # Should be a no-op
        assert parent.lines()[0] == "     "

    def test_clipping_col_beyond_width(self):
        parent = Surface(5, 5)
        sub = parent.subsurface(1, 1, 3, 3)
        sub.draw_text(0, 3, "x")
        # col >= width is a no-op
        assert parent.lines()[1] == "     "

    def test_nested_subsurface(self):
        parent = Surface(6, 6)
        sub1 = parent.subsurface(1, 1, 4, 4)
        sub2 = sub1.subsurface(1, 1, 2, 2)
        sub2.draw_text(0, 0, "z")
        assert parent.lines()[2][2] == "z"

    def test_draw_box_clipped_by_subsurface_bounds(self):
        parent = Surface(6, 6)
        sub = parent.subsurface(1, 1, 3, 3)
        sub.draw_box(0, 0, 5, 5)
        # Only 3x3 area should be affected inside the subsurface
        lines = parent.lines()
        assert lines[1][1] == "┌"
        assert lines[1][3] == "┐"
        assert lines[3][1] == "└"
        assert lines[3][3] == "┘"

    def test_fill_rect_clipped_by_subsurface_bounds(self):
        parent = Surface(5, 5)
        sub = parent.subsurface(1, 1, 2, 2)
        sub.fill_rect(0, 0, 5, 5, "#")
        lines = parent.lines()
        assert lines[1][1:3] == "##"
        assert lines[2][1:3] == "##"
        assert lines[0] == "     "
        assert lines[3] == "     "
