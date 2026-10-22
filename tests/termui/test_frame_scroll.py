# -*- coding: utf-8 -*-
"""
Module: tests/termui/test_frame_scroll.py
Description: BoxFrame's border scrollbar: hide-when-fits, geometry and placement.
Author: Zev
Date: 2026-10-21
"""

from __future__ import annotations

from pigit.termui import palette
from pigit.termui.primitives.frame import BoxFrame
from pigit.termui.surface import Surface

_THUMB = "▐"
_TRACK = "│"


def _draw(
    *,
    track=6,
    width=20,
    first=0,
    total=20,
    visible=6,
    bg=None,
    fg=None,
    style_flags=None,
):
    """Draw a frame with a scroll window and return the surface."""
    style = {}
    if bg is not None:
        style["bg"] = bg
    if fg is not None:
        style["fg"] = fg
    if style_flags is not None:
        style["style_flags"] = style_flags
    frame = BoxFrame(width, track, **style)
    frame.set_scroll(first=first, total=total, visible=visible)
    surface = Surface(width + 2, track + 2)
    frame.draw(surface, 0, 0)
    return surface


def _track(surface: Surface) -> str:
    """Characters on the right border, between the two corners."""
    return "".join(row[-1].char for row in surface.rows()[1:-1])


class TestWhenTheBarAppears:
    def test_content_that_fits_leaves_the_border_alone(self):
        assert _track(_draw(total=6, visible=6)) == _TRACK * 6

    def test_a_very_short_viewport_shows_nothing(self):
        assert _track(_draw(first=0, total=10, visible=0)) == _TRACK * 6

    def test_a_frame_with_no_room_draws_nothing(self):
        frame = BoxFrame(-1, 5)
        frame.set_scroll(first=0, total=100, visible=5)
        surface = Surface(10, 10)
        frame.draw(surface, 0, 0)
        assert _THUMB not in "".join(
            cell.char for row in surface.rows() for cell in row
        )

    def test_a_frame_with_no_track_draws_nothing(self):
        """inner_height 0 leaves only a top and bottom border; the bar must
        not land on the bottom-right corner."""
        frame = BoxFrame(20, 0)
        frame.set_scroll(first=0, total=20, visible=6)
        surface = Surface(22, 2)
        frame.draw(surface, 0, 0)
        assert _THUMB not in "".join(surface.lines())
        assert surface.lines()[1].endswith("┘")


class TestWhereTheThumbSits:
    def test_at_the_top(self):
        assert _track(_draw(first=0, total=20, visible=6)) == _THUMB + _TRACK * 5

    def test_in_the_middle(self):
        # track=6, visible=6, total=20, first=7 -> thumb=1, top=2
        assert _track(_draw(first=7, total=20, visible=6)) == (
            _TRACK * 2 + _THUMB + _TRACK * 3
        )

    def test_at_the_bottom(self):
        assert _track(_draw(first=14, total=20, visible=6)) == _TRACK * 5 + _THUMB

    def test_an_offset_past_the_end_is_clamped(self):
        assert _track(_draw(first=999, total=20, visible=6)) == _TRACK * 5 + _THUMB

    def test_a_negative_offset_stays_at_the_top(self):
        assert _track(_draw(first=-5, total=20, visible=6)) == _THUMB + _TRACK * 5


class TestHowLongTheThumbIs:
    def test_it_shrinks_as_the_content_grows(self):
        wide = _draw(track=12, total=24, visible=12)
        assert _track(wide) == _THUMB * 6 + _TRACK * 6

        wider = _draw(track=12, total=48, visible=12)
        assert _track(wider) == _THUMB * 3 + _TRACK * 9

    def test_a_tiny_fraction_keeps_one_cell(self):
        # floor(6 * 6 / 100) == 0; the minimum is what keeps the bar visible.
        assert _track(_draw(first=0, total=100, visible=6)) == _THUMB + _TRACK * 5


class TestWhatItTouches:
    def test_the_thumb_keeps_the_frame_background(self):
        surface = _draw(first=0, total=20, visible=6, bg=(1, 2, 3))
        rows = surface.rows()
        thumb_cell = rows[1][-1]
        border_cell = rows[2][-1]
        assert thumb_cell.char == _THUMB
        assert thumb_cell.bg == border_cell.bg == (1, 2, 3)

    def test_only_the_right_border_changes(self):
        """Every cell left of the border keeps its glyph *and* its style; the
        border's own cells keep their style too, only the glyph changes."""
        style = dict(fg=(9, 8, 7), bg=(1, 2, 3), style_flags=palette.STYLE_BOLD)
        plain = _draw(total=6, visible=6, **style)
        marked = _draw(first=0, total=20, visible=6, **style)
        for row_a, row_b in zip(plain.rows(), marked.rows(), strict=True):
            for cell_a, cell_b in zip(row_a[:-1], row_b[:-1], strict=True):
                assert (
                    cell_a.char,
                    cell_a.fg,
                    cell_a.bg,
                    cell_a.style_flags,
                ) == (
                    cell_b.char,
                    cell_b.fg,
                    cell_b.bg,
                    cell_b.style_flags,
                ), "only the right border may change"
            assert (
                row_b[-1].fg,
                row_b[-1].bg,
                row_b[-1].style_flags,
            ) == (
                row_a[-1].fg,
                row_a[-1].bg,
                row_a[-1].style_flags,
            ), "the thumb keeps the frame's style"

    def test_the_thumb_keeps_the_frame_style_flags(self):
        surface = _draw(first=0, total=20, visible=6, style_flags=palette.STYLE_BOLD)
        rows = surface.rows()
        assert rows[1][-1].style_flags == rows[2][-1].style_flags == palette.STYLE_BOLD

    def test_the_thumb_follows_the_frame_colour(self):
        """Borders differ per owner (accent, dim, primary); a fixed tone would
        sit darker than a primary border. Weight is what marks the thumb."""
        surface = _draw(first=0, total=20, visible=6, fg=(9, 8, 7))
        rows = surface.rows()
        assert rows[1][-1].char == _THUMB
        assert rows[1][-1].fg == rows[2][-1].fg == (9, 8, 7)
