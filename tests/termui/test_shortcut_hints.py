# -*- coding: utf-8 -*-
"""
Module: tests/termui/test_shortcut_hints.py
Description: ShortcutHints strip paint and measure.
Author: Zev
Date: 2026-08-25
"""

from __future__ import annotations

from pigit.termui.surface import Surface
from pigit.termui.theme import get_theme
from pigit.termui.widgets import (
    ShortcutHints,
    measure_shortcut_hints,
    paint_shortcut_hints,
)


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
