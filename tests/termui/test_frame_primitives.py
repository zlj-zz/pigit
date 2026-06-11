# -*- coding: utf-8 -*-
"""Tests for pigit.termui.frame_primitives."""

from __future__ import annotations

from pigit.termui._surface import Surface
from pigit.termui._frame import BoxFrame


class TestBoxFrame:
    def test_draw_and_content_rect(self):
        s = Surface(8, 5)
        frame = BoxFrame(inner_width=4, inner_height=2, title="X")
        frame.draw(s, 0, 0)
        cr, cc, cw, ch = frame.content_rect(0, 0)
        assert cr == 1 and cc == 1 and cw == 4 and ch == 2
        lines = s.lines()
        assert lines[0].startswith("┌")
        assert "X" in lines[0]

    def test_zero_inner_width(self):
        s = Surface(4, 4)
        frame = BoxFrame(inner_width=0, inner_height=1)
        frame.draw(s, 0, 0)
        lines = s.lines()
        # outer_width = 2, so just left/right borders
        assert lines[0] == "┌┐  "

    def test_content_rect_with_offset(self):
        frame = BoxFrame(inner_width=3, inner_height=2)
        cr, cc, cw, ch = frame.content_rect(5, 10)
        assert (cr, cc, cw, ch) == (6, 11, 3, 2)

    def test_outer_size_properties(self):
        frame = BoxFrame(inner_width=5, inner_height=3)
        assert frame.outer_width == 7
        assert frame.outer_height == 5

    def test_set_inner_size_updates_properties(self):
        frame = BoxFrame(inner_width=2, inner_height=1)
        assert frame.outer_width == 4
        frame.set_inner_size(10, 5)
        assert frame.outer_width == 12
        assert frame.outer_height == 7
