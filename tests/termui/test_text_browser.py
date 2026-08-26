# -*- coding: utf-8 -*-
"""
Module: tests/termui/test_text_browser.py
Description: Tests for TextBrowser public scroll/content API.
Author: Zev
Date: 2026-08-26
"""

from __future__ import annotations

from pigit.termui.widgets.text_browser import TextBrowser


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
