# -*- coding: utf-8 -*-
"""
Module: tests/termui/test_bordered_text_browser.py
Description: Tests for BorderedTextBrowser title, content, and scroll delegation.
Author: Zev
Date: 2026-08-20
"""

from __future__ import annotations

from pigit.termui.mouse import MouseButton, MouseEvent, MouseKind
from pigit.termui.segment import Segment
from pigit.termui.surface import Surface
from pigit.termui.widgets.bordered_text_browser import BorderedTextBrowser
from pigit.termui.widgets.text_browser import TextBrowser


def test_set_title_and_string_content() -> None:
    browser = BorderedTextBrowser(title="Log", id="bb")
    browser.resize((24, 8))
    browser.set_content(["line one", "line two"])
    surface = Surface(24, 8)
    browser.paint(surface)
    top = "".join(c.char for c in surface._rows[0])
    assert "Log" in top
    rows = ["".join(c.char for c in row) for row in surface._rows]
    assert any("line one" in row for row in rows)


def test_set_segment_content() -> None:
    browser = BorderedTextBrowser(id="bb")
    browser.resize((20, 6))
    browser.set_content([[Segment("HEAD", fg=(0, 255, 0))]])
    assert browser._browser.lines == ["HEAD"]


class TestBorderScrollbar:
    """The right border carries the scroll position (see BoxFrame)."""

    @staticmethod
    def _right_border(surface, frame) -> str:
        return "".join(
            surface._rows[row][-1].char for row in range(1, frame.outer_height - 1)
        )

    def test_it_follows_the_scroll(self) -> None:
        browser = BorderedTextBrowser(id="bb")
        browser.resize((20, 10))
        browser.set_content([f"row {i}" for i in range(50)])

        surface = Surface(20, 10)
        browser.paint(surface)
        assert self._right_border(surface, browser._frame).startswith("▐")

        browser.scroll_down(10**6)
        surface = Surface(20, 10)
        browser.paint(surface)
        assert self._right_border(surface, browser._frame).endswith("▐")

    def test_it_describes_the_rows_this_surface_shows(self) -> None:
        """The browser can be sized for a taller surface than the one being
        painted. The bar must follow what is drawn, not the stale viewport:
        using ``viewport_rows`` here would claim the bottom was reached."""
        browser = BorderedTextBrowser(id="bb")
        browser.resize((12, 12))
        browser.set_content([f"row {i}" for i in range(30)])
        browser.scroll_down(20)

        surface = Surface(12, 5)
        browser.paint(surface)

        # 3 painted rows, 27 rows of scroll room: offset 20 is the middle.
        assert self._right_border(surface, browser._frame) == "│▐│"

    def test_a_taller_surface_shows_all_rows_and_no_bar(self) -> None:
        """Paint resizes the browser to the surface, so a taller surface really
        does show more: nothing is hidden and there is no bar to show."""
        browser = BorderedTextBrowser(id="bb")
        browser.resize((20, 10))
        browser.set_content([f"row {i:02d}" for i in range(20)])

        surface = Surface(20, 30)
        browser.paint(surface)

        assert set(self._right_border(surface, browser._frame)) == {"│"}
        assert "row 19" in "\n".join(surface.lines())

    def test_a_narrower_surface_keeps_the_border(self) -> None:
        """Before paint resized the browser, its stale wider size painted over
        the right border -- and the scrollbar with it."""
        browser = BorderedTextBrowser(id="bb")
        browser.resize((30, 10))
        browser.set_content(["row " + "y" * 40] * 60)
        browser.scroll_down(10**6)

        surface = Surface(20, 10)
        browser.paint(surface)

        right = self._right_border(surface, browser._frame)
        assert set(right) <= {"▐", "│"}, right
        assert "▐" in right

    def test_fitting_content_leaves_the_border_alone(self) -> None:
        browser = BorderedTextBrowser(id="bb")
        browser.resize((20, 10))
        browser.set_content(["a", "b", "c"])
        surface = Surface(20, 10)
        browser.paint(surface)
        assert set(self._right_border(surface, browser._frame)) == {"│"}


def test_scroll_and_wheel_delegate() -> None:
    browser = BorderedTextBrowser(id="bb")
    browser.resize((20, 4))
    browser.set_content([f"row {i}" for i in range(30)])
    browser.scroll_down(2)
    assert browser._browser.scroll_i == 2
    down = MouseEvent(2, 2, MouseButton.WHEEL_DOWN, MouseKind.PRESS)
    assert browser.handle_mouse(down) is True
    assert browser._browser.scroll_i == 2 + TextBrowser.WHEEL_SCROLL_LINES


def test_set_title_updates_frame() -> None:
    browser = BorderedTextBrowser(title="old", id="bb")
    browser.set_title("feat")
    browser.resize((20, 6))
    browser.set_content(["* abc"])
    surface = Surface(20, 6)
    browser.paint(surface)
    top = "".join(c.char for c in surface._rows[0])
    assert "feat" in top
