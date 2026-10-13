# -*- coding: utf-8 -*-
"""
Module: tests/termui/test_shortcut_hints.py
Description: ShortcutHints strip paint, measure and click mapping.
Author: Zev
Date: 2026-08-25
"""

from __future__ import annotations

from pigit.termui.mouse import MouseButton, MouseEvent, MouseKind
from pigit.termui.surface import Surface
from pigit.termui.theme import get_theme
from pigit.termui.widgets import (
    ShortcutHints,
    measure_shortcut_hints,
    paint_shortcut_hints,
)

_PAIRS = [("Tab", "body"), ("Ctrl+Enter", "commit"), ("Esc", "cancel")]


def _press(col: int, **kwargs) -> MouseEvent:
    """A left press at 1-based *col* on the strip's only row."""
    kwargs.setdefault("button", MouseButton.LEFT)
    kwargs.setdefault("kind", MouseKind.PRESS)
    return MouseEvent(col=col, row=1, **kwargs)


def _clickable(pairs: list[tuple[str, str]], width: int | None = None):
    """A strip that records the label of every pair a click fired.

    Returns:
        ``(hints, clicked)``; ``clicked`` collects labels as they fire.
    """
    clicked: list[str] = []
    hints = ShortcutHints(pairs, on_click=clicked.append)
    hints.resize((width if width is not None else measure_shortcut_hints(pairs), 1))
    return hints, clicked


def _text_columns(pairs: list[tuple[str, str]]) -> list[tuple[int, int, str]]:
    """Spans derived from the painted text alone: ``(first_col, stop_col, label)``.

    1-based, ``stop_col`` exclusive, first pair starting after the inset. This
    is an independent reading of the strip, so it can disagree with the layout
    the widget computes -- which is the point.
    """
    spans: list[tuple[int, int, str]] = []
    cursor = 1  # the strip's leading inset
    for i, (label, desc) in enumerate(pairs):
        if i:
            cursor += 2
        text = f"{label} {desc}"
        spans.append((cursor + 1, cursor + 1 + len(text), label))
        cursor += len(text)
    return spans


def test_measure_includes_leading_gap():
    pairs = [("Tab", "body"), ("Esc", "cancel")]
    assert measure_shortcut_hints(pairs) == 1 + len("Tab body  Esc cancel")


def test_paint_and_measure_agree_on_leading_inset():
    """Direct paint_shortcut_hints callers must match measure (no col=1 hack)."""
    pairs = [("Tab", "body"), ("Esc", "cancel")]
    width = measure_shortcut_hints(pairs)
    surface = Surface(width, 1)
    paint_shortcut_hints(surface, pairs)
    # Leading inset: col 0 empty of key glyphs; first key at col 1.
    assert surface.rows()[0][0].char in ("", " ")
    assert surface.rows()[0][1].char == "T"
    # Content consumes the measured width (no trailing dead column).
    last = surface.rows()[0][width - 1]
    assert last.char not in ("", " ") or width == 1


def test_shortcut_hints_always_fills_background():
    hints = ShortcutHints([("Tab", "body")])
    hints.resize((12, 1))
    surface = Surface(12, 1)
    # Prefill with a marker color that fill must overwrite.
    surface.fill_rect_rgb(0, 0, 12, 1, (1, 2, 3))
    hints.paint(surface)
    assert surface.rows()[0][0].bg == get_theme().bg_base
    assert surface.rows()[0][11].bg == get_theme().bg_base


def test_paint_stops_at_width():
    hints = ShortcutHints([("Tab", "body"), ("Ctrl+Enter", "commit")])
    hints.resize((8, 1))
    surface = Surface(8, 1)
    hints.paint(surface)
    line = surface.lines()[0]
    assert "Tab" in line
    assert line[1] == "T"
    assert surface.rows()[0][1].fg == get_theme().fg_primary


class TestWhichColumnFiresWhichPair:
    """The strip paints and hit-tests through one layout, so a column's label
    is decided by the glyphs drawn on it. Both sides are read separately here:
    the expected spans come from the text, the actual ones from the widget."""

    def test_the_painted_line_is_the_joined_pairs(self):
        hints, _ = _clickable(_PAIRS)
        surface = Surface(hints.preferred_width, 1)
        hints.paint(surface)
        assert surface.lines()[0] == " Tab body  Ctrl+Enter commit  Esc cancel"

    def test_every_column_of_a_pair_fires_that_pair(self):
        hints, clicked = _clickable(_PAIRS)
        spans = _text_columns(_PAIRS)
        for i, (first, _stop, label) in enumerate(spans):
            # Up to the next pair's first column: the blank columns between
            # two hints answer for the hint on their left.
            stop = spans[i + 1][0] if i + 1 < len(spans) else spans[i][1]
            for col in range(first, stop):
                clicked.clear()
                assert hints.handle_mouse(_press(col)) is True
                assert clicked == [label], f"column {col} fired {clicked}"

    def test_the_trailing_pad_is_not_clickable(self):
        """Room to the right of the last pair belongs to nobody."""
        pairs = [("Tab", "body")]
        hints, clicked = _clickable(pairs, width=12)
        stop = _text_columns(pairs)[0][1]
        assert hints.handle_mouse(_press(stop - 1)) is True
        assert clicked == ["Tab"], "the pair's own last column still fires"

        clicked.clear()
        for col in range(stop, 13):
            assert hints.handle_mouse(_press(col)) is False
        assert clicked == []

    def test_the_leading_inset_is_not_clickable(self):
        """Column 0 of the strip is the gap that separates it from a sibling,
        so the first key starts at column 1."""
        hints, clicked = _clickable(_PAIRS)
        assert hints.handle_mouse(_press(1)) is False
        assert clicked == []
        assert hints.handle_mouse(_press(2)) is True
        assert clicked == ["Tab"]

    def test_a_pair_the_width_cut_off_is_not_clickable(self):
        """At width 8 only "Tab" is drawn; nothing else answers a click."""
        pairs = [("Tab", "body"), ("Ctrl+Enter", "commit")]
        hints, clicked = _clickable(pairs, width=8)
        hints.handle_mouse(_press(9))
        assert clicked == []

    def test_a_key_whose_description_was_cut_off_is_clickable(self):
        """The width check that drops the description comes after the key is
        drawn, so that key is on screen and must answer for itself."""
        pairs = [("Tab", "body")]
        hints, clicked = _clickable(pairs, width=6)
        surface = Surface(6, 1)
        hints.paint(surface)
        assert surface.lines()[0].rstrip() == " Tab"
        hints.handle_mouse(_press(4))
        assert clicked == ["Tab"]


class TestWhatCountsAsAClick:
    def test_only_a_left_press(self):
        hints, clicked = _clickable(_PAIRS)
        hints.handle_mouse(_press(2, kind=MouseKind.RELEASE))
        hints.handle_mouse(_press(2, button=MouseButton.RIGHT))
        assert clicked == []

    def test_a_drag_does_not_fire_every_pair_it_crosses(self):
        """A press that moved is a drag. `commit` sits next to `cancel`, so
        firing on motion would commit on the way past."""
        hints, clicked = _clickable(_PAIRS)
        assert hints.handle_mouse(_press(2, motion=True)) is False
        assert clicked == []

    def test_a_strip_without_a_handler_is_not_interactive(self):
        hints = ShortcutHints(_PAIRS)
        hints.resize((hints.preferred_width, 1))
        assert hints.handle_mouse(_press(2)) is False
