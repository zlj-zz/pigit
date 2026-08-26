# -*- coding: utf-8 -*-
"""
Module: tests/termui/test_bordered_browser.py
Description: Tests for BorderedBrowser title, content, and scroll delegation.
Author: Zev
Date: 2026-08-20
"""

from __future__ import annotations

from pigit.termui.mouse import MouseButton, MouseEvent, MouseKind
from pigit.termui.segment import Segment
from pigit.termui.surface import Surface
from pigit.termui.widgets.bordered_browser import BorderedBrowser
from pigit.termui.widgets.line_text_browser import LineTextBrowser


def test_set_title_and_string_content() -> None:
    browser = BorderedBrowser(title="Log", id="bb")
    browser.resize((24, 8))
    browser.set_content(["line one", "line two"])
    surface = Surface(24, 8)
    browser.paint(surface)
    top = "".join(c.char for c in surface._rows[0])
    assert "Log" in top
    rows = ["".join(c.char for c in row) for row in surface._rows]
    assert any("line one" in row for row in rows)


def test_set_segment_content() -> None:
    browser = BorderedBrowser(id="bb")
    browser.resize((20, 6))
    browser.set_content([[Segment("HEAD", fg=(0, 255, 0))]])
    assert browser._browser._content == ["HEAD"]


def test_scroll_and_wheel_delegate() -> None:
    browser = BorderedBrowser(id="bb")
    browser.resize((20, 4))
    browser.set_content([f"row {i}" for i in range(30)])
    browser.scroll_down(2)
    assert browser._browser._i == 2
    down = MouseEvent(2, 2, MouseButton.WHEEL_DOWN, MouseKind.PRESS)
    assert browser.handle_mouse(down) is True
    assert browser._browser._i == 2 + LineTextBrowser.WHEEL_SCROLL_LINES


def test_set_title_updates_frame() -> None:
    browser = BorderedBrowser(title="old", id="bb")
    browser.set_title("feat")
    browser.resize((20, 6))
    browser.set_content(["* abc"])
    surface = Surface(20, 6)
    browser.paint(surface)
    top = "".join(c.char for c in surface._rows[0])
    assert "feat" in top
