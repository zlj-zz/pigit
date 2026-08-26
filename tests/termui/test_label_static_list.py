# -*- coding: utf-8 -*-
"""
Module: tests/termui/test_label_static_list.py
Description: Label and StaticList paint contracts.
Author: Zev
Date: 2026-08-25
"""

from __future__ import annotations

from pigit.termui.surface import Surface
from pigit.termui.theme import get_theme
from pigit.termui.widgets import Label, StaticList


def test_label_paints_text():
    label = Label("Staged (2)", fg=get_theme().fg_dim)
    label.resize((20, 1))
    surface = Surface(20, 1)
    label.paint(surface)
    assert surface.lines()[0].startswith("Staged (2)")


def test_label_bg_pads_full_width():
    bg = (10, 20, 30)
    label = Label("Hi", fg=get_theme().fg_dim, bg=bg)
    label.resize((10, 1))
    surface = Surface(10, 1)
    label.paint(surface)
    for cell in surface.rows()[0]:
        assert cell.bg == bg


def test_static_list_empty_text():
    lst = StaticList([], empty_text="  No staged files")
    lst.resize((30, 3))
    surface = Surface(30, 3)
    lst.paint(surface)
    assert "No staged files" in surface.lines()[0]


def test_static_list_bg_fills_unused_rows():
    bg = (10, 20, 30)
    lst = StaticList(["a"], bg=bg)
    lst.resize((8, 3))
    surface = Surface(8, 3)
    surface.fill_rect_rgb(0, 0, 8, 3, (9, 9, 9))
    lst.paint(surface)
    assert surface.rows()[0][0].bg == bg
    assert surface.rows()[2][7].bg == bg


def test_static_list_row_style():
    theme = get_theme()

    def style(i: int, row: str):
        return theme.fg_success if i == 0 else theme.fg_danger

    lst = StaticList(["  M a.py", "  D b.py"], row_style=style)
    lst.resize((20, 2))
    surface = Surface(20, 2)
    lst.paint(surface)
    assert surface.rows()[0][2].fg == theme.fg_success
    assert surface.rows()[1][2].fg == theme.fg_danger
