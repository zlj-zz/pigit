# -*- coding: utf-8 -*-
"""
Module: tests/termui/test_option_list_chrome.py
Description: Contract tests for OptionList header/footer chrome slots.
Author: Zev
Date: 2026-08-25
"""

from __future__ import annotations

from pigit.termui.component import Component
from pigit.termui.mouse import MouseButton, MouseEvent, MouseKind
from pigit.termui.segment import Segment
from pigit.termui.surface import Surface
from pigit.termui.widgets.option_list import OptionList


class _MarkChrome(Component):
    """Paints one marker char; records lifecycle."""

    def __init__(self, mark: str) -> None:
        super().__init__()
        self.mark = mark
        self.mounted = False
        self.destroyed = False

    def mount(self) -> None:
        super().mount()
        self.mounted = True

    def unmount(self) -> None:
        super().unmount()
        self.mounted = False

    def destroy(self) -> None:
        self.destroyed = True
        super().destroy()

    def paint(self, surface: Surface) -> None:
        surface.draw_text_rgb(0, 0, self.mark)


def _click(row: int, col: int = 1) -> MouseEvent:
    return MouseEvent(col=col, row=row, button=MouseButton.LEFT, kind=MouseKind.PRESS)


def _wheel(row: int, up: bool = True) -> MouseEvent:
    btn = MouseButton.WHEEL_UP if up else MouseButton.WHEEL_DOWN
    return MouseEvent(col=1, row=row, button=btn, kind=MouseKind.PRESS)


def test_no_slots_visible_row_count_is_full_height():
    lst = OptionList(content=["a", "b", "c"], size=(20, 5))
    assert lst.visible_row_count == 5
    assert lst._header_h == 0
    assert lst._footer_h == 0


def test_header_reduces_visible_rows_and_paints_marker():
    header = _MarkChrome("H")
    lst = OptionList(content=["a", "b", "c"], size=(20, 5), header=header)
    assert lst._header_h == 1
    assert lst.visible_row_count == 4
    surface = Surface(20, 5)
    lst.paint(surface)
    assert surface.lines()[0][0] == "H"


def test_footer_click_returns_true_without_changing_selection():
    footer = _MarkChrome("F")
    lst = OptionList(content=["a", "b", "c"], size=(20, 4), footer=footer)
    lst.curr_no = 0
    assert lst.handle_mouse(_click(4)) is True
    assert lst.curr_no == 0


def test_header_click_returns_true_without_changing_selection():
    header = _MarkChrome("H")
    lst = OptionList(content=["a", "b", "c"], size=(20, 4), header=header)
    lst.curr_no = 1
    assert lst.handle_mouse(_click(1)) is True
    assert lst.curr_no == 1
    assert lst.handle_mouse(_click(2)) is True
    assert lst.curr_no == 0


def test_wheel_over_header_scrolls_list():
    header = _MarkChrome("H")
    lst = OptionList(content=["a", "b", "c", "d"], size=(20, 3), header=header)
    lst.curr_no = 0
    assert lst.handle_mouse(_wheel(1, up=False)) is True
    assert lst.curr_no == 1


def test_empty_state_stays_below_header():
    header = _MarkChrome("H")
    lst = OptionList(
        size=(20, 5),
        header=header,
        empty_state=[Segment("EMPTY")],
    )
    lst.set_content([])
    surface = Surface(20, 5)
    lst.paint(surface)
    assert surface.lines()[0][0] == "H"
    body = "\n".join(surface.lines()[1:])
    assert "EMPTY" in body
    assert "EMPTY" not in surface.lines()[0]


def test_search_bar_stays_above_footer():
    footer = _MarkChrome("F")
    lst = OptionList(content=["alpha"], size=(20, 4), footer=footer)
    lst._search_active = True
    lst._search_query = "al"
    surface = Surface(20, 4)
    lst.paint(surface)
    assert surface.lines()[3][0] == "F"
    assert "/" in surface.lines()[2] or "al" in surface.lines()[2]


def test_zero_list_height_does_not_crash():
    header = _MarkChrome("H")
    footer = _MarkChrome("F")
    lst = OptionList(content=["a"], size=(20, 2), header=header, footer=footer)
    assert lst.visible_row_count == 0
    surface = Surface(20, 2)
    lst.paint(surface)
    assert lst.handle_mouse(_click(1)) is True
    assert lst.handle_mouse(_click(2)) is True


def test_short_panel_does_not_paint_footer_outside_allocation():
    """Both slots on height 1: fit header only; never write past allocated rows."""
    header = _MarkChrome("H")
    footer = _MarkChrome("F")
    lst = OptionList(content=["a"], size=(20, 1), header=header, footer=footer)
    assert lst._header_h == 1
    assert lst._footer_h == 0
    root = Surface(20, 3)
    lst.paint(root)
    assert root.lines()[0][0] == "H"
    assert root.lines()[1] == " " * 20
    assert root.lines()[2] == " " * 20


def test_past_list_without_footer_returns_false():
    """Subclass-reduced viewport must not swallow clicks below the list."""

    class _InsetList(OptionList):
        @property
        def visible_row_count(self) -> int:
            return max(0, self._size[1] - 3)

    lst = _InsetList(content=["a", "b", "c"], size=(20, 10))
    lst.curr_no = 0
    # Rows 8-10 (1-based) are below the 7-row list band; no footer slot.
    assert lst.handle_mouse(_click(8)) is False
    assert lst.curr_no == 0


def test_slots_lifecycle_forwarded_and_not_in_children():
    header = _MarkChrome("H")
    footer = _MarkChrome("F")
    lst = OptionList(content=["a"], size=(20, 5), header=header, footer=footer)
    assert header not in lst.children
    assert footer not in lst.children
    lst.mount()
    assert header.mounted and footer.mounted
    lst.unmount()
    assert not header.mounted and not footer.mounted
    lst.destroy()
    assert header.destroyed and footer.destroyed


def test_sizeless_init_syncs_bands_on_first_resize():
    header = _MarkChrome("H")
    lst = OptionList(content=["a"], header=header)
    assert lst._size == (0, 0)
    assert lst._header_h == 0
    lst.resize((20, 5))
    assert lst._header_h == 1
    assert lst.visible_row_count == 4


class _TallFooter(Component):
    """Footer that wants a fixed multi-row height via ``chrome_band_height``."""

    def __init__(self, want: int, mark: str = "F") -> None:
        super().__init__()
        self.want = want
        self.mark = mark
        self.wheel_hits = 0

    def chrome_band_height(self, width: int, panel_height: int) -> int:
        del width, panel_height
        return self.want

    def paint(self, surface: Surface) -> None:
        for row in range(surface.height):
            surface.draw_text_rgb(row, 0, self.mark)

    def handle_mouse(self, event: MouseEvent) -> bool:
        if event.button in (MouseButton.WHEEL_LEFT, MouseButton.WHEEL_RIGHT):
            self.wheel_hits += 1
            return True
        return False


def test_chrome_band_height_multi_row_footer():
    footer = _TallFooter(3)
    lst = OptionList(content=["a", "b", "c", "d"], size=(20, 8), footer=footer)
    assert lst._footer_h == 3
    assert lst.visible_row_count == 5
    surface = Surface(20, 8)
    lst.paint(surface)
    assert surface.lines()[5][0] == "F"
    assert surface.lines()[7][0] == "F"


def test_chrome_band_all_or_nothing_when_too_tall():
    footer = _TallFooter(5)
    lst = OptionList(content=["a"], size=(20, 4), footer=footer)
    assert lst._footer_h == 0
    assert lst.visible_row_count == 4


def test_invalidate_chrome_bands_refits_after_policy_change():
    footer = _TallFooter(3)
    lst = OptionList(content=["a", "b"], size=(20, 8), footer=footer)
    assert lst._footer_h == 3
    footer.want = 0
    lst.invalidate_chrome_bands()
    assert lst._footer_h == 0
    assert lst.visible_row_count == 8


def test_footer_horizontal_wheel_consumed():
    footer = _TallFooter(2)
    lst = OptionList(content=["a", "b", "c"], size=(20, 6), footer=footer)
    lst.curr_no = 0
    left = MouseEvent(col=1, row=5, button=MouseButton.WHEEL_LEFT, kind=MouseKind.PRESS)
    assert lst.handle_mouse(left) is True
    assert footer.wheel_hits == 1
    assert lst.curr_no == 0
