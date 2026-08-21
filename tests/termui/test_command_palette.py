"""
Module: tests/termui/test_command_palette.py
Description: Unit tests for the generic termui CommandPalette widget.
Author: Zev
Date: 2026-08-20
"""

from __future__ import annotations

from pigit.termui import keys
from pigit.termui.surface import Surface
from pigit.termui.widgets import CommandPalette, PaletteItem, list_slots_for_term

_ITEMS = [
    PaletteItem("alpha", "First"),
    PaletteItem("beta", "Second"),
    PaletteItem("gamma", "Third"),
]


def _ids(palette: CommandPalette) -> list[str]:
    return [c.id for c in palette._candidates]


class TestListSlots:
    def test_clamps_to_minmax(self):
        assert list_slots_for_term(12) >= 3
        assert list_slots_for_term(80) <= 10


class TestCommandPalette:
    def test_init_inactive(self):
        palette = CommandPalette(items=_ITEMS)
        assert not palette.is_active
        assert palette._input_line.value == ""

    def test_open_close(self):
        palette = CommandPalette(items=_ITEMS, list_slots=10)
        palette.open()
        assert palette.is_active
        assert _ids(palette) == ["alpha", "beta", "gamma"]
        palette.close()
        assert not palette.is_active

    def test_open_shows_full_catalog_when_fits(self):
        palette = CommandPalette(items=_ITEMS, list_slots=10)
        palette.open()
        assert len(palette._candidates) == 3

    def test_fits_when_within_list_slots(self):
        items = [PaletteItem(f"c{i}", f"d{i}") for i in range(9)]
        palette = CommandPalette(items=items, list_slots=10)
        palette.open()
        assert len(palette._candidates) == 9
        assert palette._matched[-1].id == "c8"

    def test_down_scrolls_when_over_slots(self):
        items = [PaletteItem(f"c{i}", f"d{i}") for i in range(12)]
        palette = CommandPalette(items=items, list_slots=5)
        palette.open()
        assert len(palette._candidates) == 5
        for _ in range(5):
            palette.handle_key(keys.KEY_DOWN)
        assert palette._selected == 5
        assert palette._matched[palette._selected].id == "c5"
        assert "c5" in _ids(palette)
        assert "c0" not in _ids(palette)

    def test_down_scroll_cue_on_last_visible(self):
        items = [PaletteItem(f"c{i}", f"d{i}") for i in range(12)]
        palette = CommandPalette(items=items, list_slots=5)
        palette.open()
        surface = Surface(40, 12)
        palette.resize((40, 12))
        palette._render_surface(surface)
        assert "↓7" in "".join(surface.lines())

    def test_filter_substring(self):
        palette = CommandPalette(items=_ITEMS, list_slots=10)
        palette.open()
        palette.handle_key("a")
        palette.handle_key("l")
        assert "alpha" in _ids(palette)
        assert "beta" not in _ids(palette)

    def test_filter_matches_description(self):
        palette = CommandPalette(items=_ITEMS, list_slots=10)
        palette.open()
        for ch in "seco":
            palette.handle_key(ch)
        assert _ids(palette) == ["beta"]

    def test_up_down_selection(self):
        palette = CommandPalette(items=_ITEMS, list_slots=10)
        palette.open()
        assert palette._selected == 0
        palette.handle_key(keys.KEY_DOWN)
        assert palette._selected == 1
        palette.handle_key(keys.KEY_UP)
        assert palette._selected == 0

    def test_enter_executes_selected(self):
        executed: list[str] = []
        palette = CommandPalette(
            items=_ITEMS,
            list_slots=10,
            on_execute=lambda item: executed.append(item),
        )
        palette.open()
        palette.handle_key(keys.KEY_DOWN)
        palette.handle_key(keys.KEY_ENTER)
        assert executed == ["beta"]

    def test_enter_passes_typed_value_without_match(self):
        executed: list[str] = []
        palette = CommandPalette(
            items=_ITEMS,
            list_slots=10,
            on_execute=lambda item: executed.append(item),
        )
        palette.open()
        for ch in "zeta":
            palette.handle_key(ch)
        palette.handle_key(keys.KEY_ENTER)
        assert executed == ["zeta"]

    def test_esc_dismisses_without_execute(self):
        executed: list[str] = []
        dismissed = []
        palette = CommandPalette(
            items=_ITEMS,
            list_slots=10,
            on_execute=lambda item: executed.append(item),
            on_dismiss=lambda: dismissed.append(True),
        )
        palette.open()
        palette.handle_key("a")
        palette.handle_key(keys.KEY_ESC)
        assert not palette.is_active
        assert executed == []
        assert dismissed == [True]

    def test_preferred_sheet_height_uses_list_slots(self):
        items = [PaletteItem(f"c{i}") for i in range(12)]
        palette = CommandPalette(items=items, list_slots=5)
        # border + 5 list slots + rule + prompt
        assert palette.preferred_sheet_height() == 8

    def test_preferred_sheet_height_shrinks_when_few_items(self):
        palette = CommandPalette(items=_ITEMS, list_slots=10)
        assert palette.preferred_sheet_height() == 6

    def test_render_inactive(self):
        palette = CommandPalette(items=_ITEMS)
        surface = Surface(20, 5)
        palette._render_surface(surface)
        assert all(c.char == " " for row in surface._rows for c in row)

    def test_render_active_separates_list_and_input(self):
        palette = CommandPalette(items=_ITEMS, list_slots=10)
        palette.open()
        surface = Surface(40, 6)
        palette.resize((40, 6))
        palette._render_surface(surface)
        lines = surface.lines()
        assert ">" in lines[-1]
        assert "alpha" in "".join(lines)
        assert "─" in lines[-2]

    def test_render_active_skips_overlay_fill(self):
        from pigit.termui.theme import get_theme

        palette = CommandPalette(items=_ITEMS, list_slots=10)
        palette.open()
        surface = Surface(40, 5)
        palette.resize((40, 5))
        palette._render_surface(surface)
        overlay = get_theme().bg_overlay
        assert surface.rows()[-1][0].bg != overlay
