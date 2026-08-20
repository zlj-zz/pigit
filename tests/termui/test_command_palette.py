# -*- coding: utf-8 -*-
"""
Module: tests/termui/test_command_palette.py
Description: Unit tests for the generic termui CommandPalette widget.
Author: Zev
Date: 2026-08-20
"""

from __future__ import annotations

from pigit.termui import keys
from pigit.termui.surface import Surface
from pigit.termui.widgets import CommandPalette

_ITEMS = ["alpha", "beta", "gamma"]


class TestCommandPalette:
    def test_init_inactive(self):
        palette = CommandPalette(items=_ITEMS)
        assert not palette.is_active
        assert palette._input_line.value == ""

    def test_open_close(self):
        palette = CommandPalette(items=_ITEMS)
        palette.open()
        assert palette.is_active
        palette.close()
        assert not palette.is_active

    def test_filter_substring(self):
        palette = CommandPalette(items=_ITEMS)
        palette.open()
        palette.handle_key("a")
        palette.handle_key("l")
        assert "alpha" in palette._candidates
        assert "beta" not in palette._candidates

    def test_up_down_selection(self):
        palette = CommandPalette(items=_ITEMS)
        palette.open()
        palette.handle_key("a")
        assert palette._selected == 0
        palette.handle_key(keys.KEY_DOWN)
        assert palette._selected == 1
        palette.handle_key(keys.KEY_UP)
        assert palette._selected == 0

    def test_enter_executes_selected(self):
        executed: list[str] = []
        palette = CommandPalette(
            items=_ITEMS,
            on_execute=lambda item: executed.append(item),
        )
        palette.open()
        palette.handle_key("a")
        palette.handle_key(keys.KEY_ENTER)
        assert executed == ["alpha"]

    def test_enter_executes_typed_value_without_match(self):
        executed: list[str] = []
        palette = CommandPalette(
            items=_ITEMS,
            on_execute=lambda item: executed.append(item),
        )
        palette.open()
        palette.handle_key("z")
        palette.handle_key("e")
        palette.handle_key("t")
        palette.handle_key("a")
        palette.handle_key(keys.KEY_ENTER)
        assert executed == ["zeta"]

    def test_esc_dismisses_without_execute(self):
        executed: list[str] = []
        dismissed = []
        palette = CommandPalette(
            items=_ITEMS,
            on_execute=lambda item: executed.append(item),
            on_dismiss=lambda: dismissed.append(True),
        )
        palette.open()
        palette.handle_key("a")
        palette.handle_key(keys.KEY_ESC)
        assert not palette.is_active
        assert executed == []
        assert dismissed == [True]

    def test_render_inactive(self):
        palette = CommandPalette(items=_ITEMS)
        surface = Surface(20, 5)
        palette._render_surface(surface)
        assert all(
            c.char == " " for row in surface._rows for c in row
        )

    def test_render_active(self):
        palette = CommandPalette(items=_ITEMS)
        palette.open()
        surface = Surface(20, 5)
        palette.resize((20, 5))
        palette._render_surface(surface)
        lines = surface.lines()
        assert ">" in lines[-1]
