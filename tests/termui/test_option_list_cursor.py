# -*- coding: utf-8 -*-
"""
Module: tests/termui/test_option_list_cursor.py
Description: Contract tests for OptionList cursor column (glyph / ACCENT_BAR / empty).
Author: Zev
Date: 2026-08-26
"""

from __future__ import annotations

from pigit.termui import palette
from pigit.termui.segment import Segment
from pigit.termui.surface import Surface
from pigit.termui.theme import get_theme
from pigit.termui.widgets.option_list import ACCENT_BAR, OptionList


class _GlyphPanel(OptionList):
    CURSOR = "\u25cf"

    def describe_row(
        self, idx, is_cursor, *, item_idx=None, sub_row=0
    ) -> tuple[list[Segment], list[Segment] | None, list[Segment]]:
        return (
            [Segment(self.content[idx], fg=get_theme().fg_primary)],
            None,
            [],
        )


class _AccentPanel(OptionList):
    CURSOR = ACCENT_BAR

    def describe_row(
        self, idx, is_cursor, *, item_idx=None, sub_row=0
    ) -> tuple[list[Segment], list[Segment] | None, list[Segment]]:
        return (
            [Segment(self.content[idx], fg=get_theme().fg_primary)],
            None,
            [],
        )


class _NoMarkPanel(OptionList):
    CURSOR = ""

    def describe_row(
        self, idx, is_cursor, *, item_idx=None, sub_row=0
    ) -> tuple[list[Segment], list[Segment] | None, list[Segment]]:
        return (
            [Segment(self.content[idx], fg=get_theme().fg_primary)],
            None,
            [],
        )


def test_cursor_empty_leaves_describe_row_left_unchanged():
    lst = _NoMarkPanel(content=["a", "b"], size=(10, 4))
    left, _, _ = lst.describe_row(0, is_cursor=True)
    assert lst._with_cursor_mark(left, is_cursor=True) == list(left)


def test_cursor_glyph_prepended_by_option_list():
    lst = _GlyphPanel(content=["a", "b"], size=(10, 4))
    lst.curr_no = 0
    surface = Surface(10, 4)
    lst.resize((10, 4))
    lst.paint(surface)
    rows = surface.rows()
    assert rows[0][0].char == "\u25cf"
    assert rows[0][1].char == "a"
    assert rows[1][0].char == " "
    assert rows[1][1].char == "b"


def test_cursor_accent_bar_uses_brand_color():
    theme = get_theme()
    lst = _AccentPanel(content=["a", "b"], size=(10, 4))
    lst.curr_no = 0
    surface = Surface(10, 4)
    lst.resize((10, 4))
    lst.paint(surface)
    rows = surface.rows()
    assert rows[0][0].char == ACCENT_BAR
    assert rows[0][0].fg == theme.fg_accent
    assert rows[0][1].char == "a"
    assert rows[1][0].char == " "
    assert rows[1][0].fg == theme.fg_dim
    assert rows[1][1].char == "b"


def test_cursor_accent_bar_bold_on_cursor_cell():
    lst = _AccentPanel(content=["a", "b"], size=(10, 4))
    lst.curr_no = 0
    surface = Surface(10, 4)
    lst.resize((10, 4))
    lst.paint(surface)
    cell = surface.rows()[0][0]
    assert cell.style_flags & palette.STYLE_BOLD


def test_cursor_accent_dims_on_inactive_panel():
    """Off-focus panels keep the navigation anchor but drop the brand accent."""
    from pigit.termui._runtime_context import (
        RuntimeContext,
        _runtime_ctx,
        reset_focus_manager,
        reset_overlay_host,
        set_focus_manager,
        set_overlay_host,
    )
    from pigit.termui.component import Component
    from pigit.termui.containers import Column
    from pigit.termui.root import ComponentRoot

    class _Dummy(Component):
        def paint(self, surface) -> None:
            pass

    lst = _AccentPanel(content=["a", "b"], size=(10, 4))
    active = _Dummy()
    runtime = RuntimeContext()
    token = _runtime_ctx.set(runtime)
    try:
        root = ComponentRoot(Column([active, lst], heights=[1, "flex"]))
        root.resize((12, 6))
        set_overlay_host(root)
        set_focus_manager(root._focus_manager)
        root._focus_manager.set_focus_chain(active)
        assert lst.is_presentation_active() is False

        surface = Surface(10, 4)
        lst.resize((10, 4))
        lst.paint(surface)
        cell = surface.rows()[0][0]
        assert cell.char == ACCENT_BAR
        assert cell.fg == get_theme().fg_dim
        assert not (cell.style_flags & palette.STYLE_BOLD)
    finally:
        reset_focus_manager()
        reset_overlay_host()
        _runtime_ctx.reset(token)


def test_cursor_glyph_dims_on_inactive_panel():
    """Glyph cursor mark softens via presentation_fg like the row text."""
    from pigit.termui._runtime_context import (
        RuntimeContext,
        _runtime_ctx,
        reset_focus_manager,
        reset_overlay_host,
        set_focus_manager,
        set_overlay_host,
    )
    from pigit.termui.component import Component
    from pigit.termui.containers import Column
    from pigit.termui.root import ComponentRoot

    class _Dummy(Component):
        def paint(self, surface) -> None:
            pass

    theme = get_theme()
    lst = _GlyphPanel(content=["a", "b"], size=(10, 4))
    active = _Dummy()
    runtime = RuntimeContext()
    token = _runtime_ctx.set(runtime)
    try:
        root = ComponentRoot(Column([active, lst], heights=[1, "flex"]))
        root.resize((12, 6))
        set_overlay_host(root)
        set_focus_manager(root._focus_manager)
        root._focus_manager.set_focus_chain(active)
        assert lst.is_presentation_active() is False

        surface = Surface(10, 4)
        lst.resize((10, 4))
        lst.paint(surface)
        cell = surface.rows()[0][0]
        assert cell.char == "\u25cf"
        assert cell.fg == theme.fg_muted
        assert cell.fg != theme.fg_primary
    finally:
        reset_focus_manager()
        reset_overlay_host()
        _runtime_ctx.reset(token)
