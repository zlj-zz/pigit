# -*- coding: utf-8 -*-
"""
Module: tests/termui/test_text_browser.py
Description: Tests for TextBrowser public scroll/content API.
Author: Zev
Date: 2026-08-26
"""

from __future__ import annotations

from pigit.termui.widgets.text_browser import TextBrowser, block_inset, block_inset_for


def test_text_browser_scroll_i_and_replace_lines() -> None:
    b = TextBrowser(content=["a", "b", "c"], size=(10, 2), bg=None)
    assert b.lines == ["a", "b", "c"]
    assert b.scroll_i == 0
    assert b.viewport_rows == 2
    b.scroll_down(1)
    assert b.scroll_i == 1
    b.replace_lines(["x", "y"], scroll_i=0)
    assert b.lines == ["x", "y"]
    assert b.scroll_i == 0


def test_scroll_i_clamps_to_viewport() -> None:
    b = TextBrowser(content=["p", "q", "r"], size=(10, 2), bg=None)
    b.scroll_i = 999
    assert b.scroll_i == 1  # len 3, viewport 2 → max 1
    b.replace_lines(["p", "q", "r"], scroll_i=2)
    assert b.scroll_i == 1


def test_resize_preserves_scroll_across_viewport_cycle() -> None:
    """Shrinking then restoring viewport must not permanently clamp deep scroll."""
    lines = [f"line {i}" for i in range(40)]
    b = TextBrowser(content=lines, size=(10, 8), bg=None)
    b.scroll_i = 32
    assert b.scroll_i == 32
    b.resize((10, 18))
    assert b.scroll_i == 32
    b.resize((10, 8))
    assert b.scroll_i == 32


def test_block_inset_center_align_shifts_paint() -> None:
    from pigit.termui import Segment
    from pigit.termui.surface import Surface

    rows = [[Segment("Hello")]]
    browser = TextBrowser(
        content=rows,
        size=(20, 1),
        bg=None,
        content_inset=block_inset_for("center"),
    )
    surface = Surface(20, 1)
    browser.paint(surface)
    inset = block_inset(20, rows, align="center")
    assert surface.lines()[0].startswith(" " * inset + "Hello")


def test_content_valign_centers_short_content() -> None:
    from pigit.termui import Segment
    from pigit.termui.surface import Surface

    rows = [[Segment("One")], [Segment("Two")]]
    browser = TextBrowser(
        content=rows,
        size=(20, 6),
        bg=None,
        content_valign="center",
    )
    surface = Surface(20, 6)
    browser.paint(surface)
    assert surface.lines()[2].strip() == "One"
    assert surface.lines()[3].strip() == "Two"


def test_block_inset_alignments() -> None:
    from pigit.termui import Segment

    rows = [[Segment("Hi")]]
    assert block_inset(20, rows, align="left") == 2
    assert block_inset(20, rows, align="center") == 9
    assert block_inset(20, rows, align="right") == 16
