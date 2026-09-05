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
    CURSOR_ACCENT = True

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


# ---- Multi-row sub-row navigation (commit z-expand) ----


class _MultiRowPanel(OptionList):
    CURSOR = ACCENT_BAR

    def describe_row(
        self, idx, is_cursor, *, item_idx=None, sub_row=0
    ) -> tuple[list[Segment], list[Segment] | None, list[Segment]]:
        return (
            [Segment(self.content[idx] or f"r{idx}", fg=get_theme().fg_primary)],
            None,
            [],
        )


def _multirow_panel() -> _MultiRowPanel:
    """3 items × 3 rows: starts [0, 3, 6], content length 9."""
    panel = _MultiRowPanel(content=[""] * 9, size=(20, 10))
    panel.set_item_starts([0, 3, 6])
    return panel


class TestSubRowNavigation:
    def test_next_within_item_moves_sub(self):
        panel = _multirow_panel()
        panel.curr_no = 0
        panel.next()
        assert (panel.curr_no, panel._cursor_sub) == (0, 1)
        panel.next()
        assert (panel.curr_no, panel._cursor_sub) == (0, 2)

    def test_next_cross_item_lands_first_sub(self):
        """S2: forward crossing lands on the next item's first sub-row."""
        panel = _multirow_panel()
        panel.curr_no = 0
        panel._cursor_sub = 2
        panel.next()
        assert (panel.curr_no, panel._cursor_sub) == (1, 0)

    def test_previous_within_item_moves_sub(self):
        panel = _multirow_panel()
        panel.curr_no = 1
        panel._cursor_sub = 2
        panel.previous()
        assert (panel.curr_no, panel._cursor_sub) == (1, 1)

    def test_previous_cross_item_lands_last_sub(self):
        """S2: backward crossing lands on the previous item's last sub-row."""
        panel = _multirow_panel()
        panel.curr_no = 1
        panel.previous()
        assert (panel.curr_no, panel._cursor_sub) == (0, 2)

    def test_span_one_items_jump_directly(self):
        panel = _MultiRowPanel(content=[""] * 3, size=(20, 10))
        panel.set_item_starts([0, 1, 2])
        panel.curr_no = 0
        panel.next()
        assert (panel.curr_no, panel._cursor_sub) == (1, 0)
        panel.previous()
        assert (panel.curr_no, panel._cursor_sub) == (0, 0)

    def test_end_of_list_stays_put(self):
        panel = _multirow_panel()
        panel.curr_no = 2
        panel._cursor_sub = 2
        panel.next()
        assert (panel.curr_no, panel._cursor_sub) == (2, 2)

    def test_top_of_list_stays_put(self):
        panel = _multirow_panel()
        panel.curr_no = 0
        panel.previous()
        assert (panel.curr_no, panel._cursor_sub) == (0, 0)

    def test_multi_row_skips_separator_items(self):
        """Separator items are skipped whole; sub resets on the far side."""
        panel = _MultiRowPanel(content=[""] * 5, size=(20, 10))
        panel.set_item_starts([0, 2, 3])
        panel.set_skip_indices({1})
        panel.curr_no = 0
        panel._cursor_sub = 1
        panel.next()
        assert (panel.curr_no, panel._cursor_sub) == (2, 0)
        panel.previous()
        assert (panel.curr_no, panel._cursor_sub) == (0, 1)

    def test_curr_no_stable_while_walking_sub_rows(self):
        """Selection semantics: sub-row movement never changes the item."""
        panel = _multirow_panel()
        panel.curr_no = 1
        for _ in range(2):
            panel.next()
        panel.previous()
        assert panel.curr_no == 1


class TestSubRowState:
    def test_cursor_row_follows_sub(self):
        panel = _multirow_panel()
        panel.curr_no = 1
        panel._cursor_sub = 2
        assert panel.cursor_row() == 3 + 2

    def test_set_item_starts_resets_sub(self):
        panel = _multirow_panel()
        panel._cursor_sub = 2
        panel.set_item_starts([0, 3, 6])
        assert panel._cursor_sub == 0

    def test_set_item_starts_none_resets_sub(self):
        panel = _multirow_panel()
        panel._cursor_sub = 2
        panel.set_item_starts(None)
        assert panel._cursor_sub == 0

    def test_set_content_resets_sub(self):
        panel = _multirow_panel()
        panel._cursor_sub = 2
        panel.set_content(["x", "y"])
        assert panel._cursor_sub == 0

    def test_filter_resets_sub(self):
        panel = _multirow_panel()
        panel.set_source_content(["aa", "bb"])
        panel.set_item_starts([0, 1])
        panel._cursor_sub = 1
        panel.set_filter("a")
        assert panel._cursor_sub == 0
        assert panel._item_starts is None

    def test_cursor_mark_paints_on_sub_row(self):
        panel = _multirow_panel()
        panel.curr_no = 0
        panel._cursor_sub = 1
        surface = Surface(20, 10)
        panel.resize((20, 10))
        panel.paint(surface)
        rows = surface.rows()
        assert rows[1][0].char == ACCENT_BAR  # highlight on the sub-row
        assert rows[0][0].char == " "

    def test_next_scrolls_to_keep_sub_row_visible(self):
        panel = _MultiRowPanel(content=[""] * 10, size=(20, 4))
        panel.set_item_starts([0, 5])
        panel.resize((20, 4))
        for _ in range(4):
            panel.next()
        assert panel.cursor_row() == 4
        assert panel._r_start == 1  # viewport followed the sub-row


class TestCompactModeUnchanged:
    def test_compact_next_previous_unchanged(self):
        panel = _MultiRowPanel(content=["a", "b", "c"], size=(20, 10))
        panel.curr_no = 0
        panel.next()
        panel.next()
        assert panel.curr_no == 2
        panel.previous()
        assert panel.curr_no == 1

    def test_compact_cursor_row_is_item_row(self):
        panel = _MultiRowPanel(content=["a", "b", "c"], size=(20, 10))
        panel.curr_no = 2
        assert panel.cursor_row() == 2
        assert panel._cursor_sub == 0
