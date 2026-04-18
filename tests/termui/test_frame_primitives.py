# -*- coding: utf-8 -*-
"""Tests for pigit.termui.frame_primitives."""

from __future__ import annotations

from pigit.termui._surface import Surface
from pigit.termui._frame import BoxFrame


class TestBoxFrame:
    def test_draw_onto_and_content(self):
        s = Surface(8, 5)
        frame = BoxFrame(inner_width=4, inner_height=2, title="X")
        frame.draw_onto(s, 0, 0)
        frame.draw_content(s, 0, 0, ["ab", "cd"])
        lines = s.lines()
        assert lines[0].startswith("┌")
        assert "ab" in lines[1]
        assert "cd" in lines[2]

    def test_draw_content_clipped_to_inner_height(self):
        s = Surface(6, 4)
        frame = BoxFrame(inner_width=2, inner_height=1)
        frame.draw_onto(s, 0, 0)
        frame.draw_content(s, 0, 0, ["ab", "cd"])
        lines = s.lines()
        assert "ab" in lines[1]
        assert "cd" not in lines[1]  # clipped
        # row 2 is the bottom border of the box frame
        assert lines[2].startswith("└")

    def test_zero_inner_width(self):
        s = Surface(4, 4)
        frame = BoxFrame(inner_width=0, inner_height=1)
        frame.draw_onto(s, 0, 0)
        lines = s.lines()
        # outer_width = 2, so just left/right borders
        assert lines[0] == "┌┐  "

    def test_draw_content_pads_cjk_by_display_width(self):
        s = Surface(8, 4)
        frame = BoxFrame(inner_width=4, inner_height=1)
        frame.draw_onto(s, 0, 0)
        frame.draw_content(s, 0, 0, ["中"])
        lines = s.lines()
        # "中" is width 2, so it should be padded to 4 columns with 2 trailing spaces
        assert lines[1].startswith("│中  │")

    def test_draw_content_truncates_cjk_by_display_width(self):
        s = Surface(8, 4)
        frame = BoxFrame(inner_width=4, inner_height=1)
        frame.draw_onto(s, 0, 0)
        frame.draw_content(s, 0, 0, ["中文长"])
        lines = s.lines()
        # Should truncate to 3 display columns + ellipsis or pad to exactly inner_width
        assert "中" in lines[1]
        assert len(lines[1]) == 6  # │ + 4 inner + │
