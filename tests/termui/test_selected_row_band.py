# -*- coding: utf-8 -*-
"""
Module: tests/termui/test_selected_row_band.py
Description: The cursor row's selection band — declared once, drawn across the row.
Author: Zev
Date: 2026-10-13
"""

from __future__ import annotations

from dataclasses import dataclass

from pigit.termui.segment import Segment
from pigit.termui.surface import Surface
from pigit.termui.theme import Theme, get_theme, selected_row_bg, set_theme
from pigit.termui.widgets import OptionList

BAND = (10, 20, 30)
INACTIVE = (1, 2, 3)
OWN = (200, 100, 50)


@dataclass(frozen=True)
class _BandTheme(Theme):
    bg_commit_selected: tuple[int, int, int] = BAND
    bg_commit_selected_inactive: tuple[int, int, int] = INACTIVE


class _List(OptionList):
    """One row, whose band is declared on its first segment and nowhere else.

    ``left`` carries a **second** segment on purpose: the band is declared on
    the first one, so the second is the case that has to be filled by the
    draw's fallback. A one-segment left would cover for a missing fallback and
    hide the very hole this is here to catch.
    """

    CURSOR = "▎"
    CURSOR_ACCENT = True

    def describe_row(self, idx, is_cursor, *, item_idx=None, sub_row=0):
        left = [Segment("a"), Segment("b")]
        main = [Segment(" middle ")]
        right = [Segment("right")]
        self._band_cursor_row(left, is_cursor)
        return left, main, right


def _painted(rows: int = 3) -> list[list]:
    widget = _List(content=["row", "row", "row"])
    surface = Surface(24, rows)
    widget.resize((24, rows))
    widget.paint(surface)
    return surface.rows()


def _with_band_theme(fn):
    old = get_theme()
    set_theme(_BandTheme())
    try:
        return fn()
    finally:
        set_theme(old)


def test_one_declaration_covers_the_whole_row():
    """The row's own background has to reach the gaps and the trailing space --
    a band with the text punched out of it is not a band."""
    rows = _with_band_theme(_painted)
    cursor = rows[0]
    assert [cell.bg for cell in cursor] == [BAND] * 24


def test_the_cursor_mark_carries_it_too():
    rows = _with_band_theme(_painted)
    assert rows[0][0].char == "▎"
    assert rows[0][0].bg == BAND


def test_a_row_with_no_band_is_untouched():
    rows = _with_band_theme(_painted)
    for row in rows[1:]:
        assert [cell.bg for cell in row] == [None] * 24


def test_a_row_that_declares_nothing_gets_no_band():
    """A list that never calls `_band_cursor_row` paints exactly as before --
    this is what keeps pickers and the other sheets out of the change."""

    class _Plain(_List):
        def describe_row(self, idx, is_cursor, *, item_idx=None, sub_row=0):
            return [Segment("a")], [Segment(" middle ")], [Segment("right")]

    widget = _Plain(content=["row", "row", "row"])
    surface = Surface(24, 3)
    widget.resize((24, 3))
    widget.paint(surface)
    for row in surface.rows():
        assert [cell.bg for cell in row] == [None] * 24


def test_an_empty_left_does_not_raise():
    """`describe_row` returns `([], None, [])` for an out-of-range index; the
    band has nowhere to go, and must not be indexed into."""

    class _Empty(_List):
        def describe_row(self, idx, is_cursor, *, item_idx=None, sub_row=0):
            left: list[Segment] = []
            self._band_cursor_row(left, is_cursor)
            return left, None, []

    widget = _Empty(content=["row"])
    surface = Surface(24, 1)
    widget.resize((24, 1))
    widget.paint(surface)  # must not raise


def test_a_segment_with_its_own_background_wins():
    """`_draw_segments` fills only the segments that carry none, so a caller
    that colours one segment itself still gets that colour."""
    widget = _List(content=["row"])
    surface = Surface(10, 1)
    widget._draw_segments(
        surface,
        0,
        0,
        [Segment("a", bg=OWN), Segment("b")],
        bg=BAND,
    )
    row = surface.rows()[0]
    assert row[0].bg == OWN
    assert row[1].bg == BAND


def test_the_inactive_band_comes_from_its_own_slot():
    theme = _BandTheme()
    assert selected_row_bg(theme, active=True) == BAND
    assert selected_row_bg(theme, active=False) == INACTIVE


def test_a_theme_without_the_slots_falls_back_to_hover():
    plain = Theme()
    assert selected_row_bg(plain, active=True) == plain.bg_hover
    assert selected_row_bg(plain, active=False) == plain.bg_hover
