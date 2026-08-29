"""
Module: tests/termui/test_command_palette.py
Description: Unit tests for the generic termui CommandPalette widget.
Author: Zev
Date: 2026-08-20
"""

from __future__ import annotations

from unittest.mock import patch

from pigit.termui import keys
from pigit.termui.surface import Surface
from pigit.termui.widgets import (
    CommandPalette,
    PaletteArgs,
    PaletteItem,
    list_slots_for_term,
)
from pigit.termui.widgets.command_palette import MAX_MATCHED

_ITEMS = [
    PaletteItem("alpha", "First"),
    PaletteItem("beta", "Second"),
    PaletteItem("gamma", "Third"),
]


def _ids(palette: CommandPalette) -> list[str]:
    return [c.id for c in palette._candidates]


def _type(palette: CommandPalette, text: str) -> None:
    for ch in text:
        palette.handle_key(ch)


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
        palette.paint(surface)
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

    def test_preferred_sheet_height_does_not_overwrite_list_slots(self):
        items = [PaletteItem(f"c{i}") for i in range(12)]
        palette = CommandPalette(items=items, list_slots=5)
        assert palette.preferred_sheet_height(80) == 8
        assert palette._list_slots == 5

    def test_preferred_sheet_height_shrinks_when_few_items(self):
        palette = CommandPalette(items=_ITEMS, list_slots=10)
        assert palette.preferred_sheet_height() == 6

    def test_render_inactive(self):
        palette = CommandPalette(items=_ITEMS)
        surface = Surface(20, 5)
        palette.paint(surface)
        assert all(c.char == " " for row in surface._rows for c in row)

    def test_render_active_separates_list_and_input(self):
        palette = CommandPalette(items=_ITEMS, list_slots=10)
        palette.open()
        surface = Surface(40, 6)
        palette.resize((40, 6))
        palette.paint(surface)
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
        palette.paint(surface)
        overlay = get_theme().bg_overlay
        assert surface.rows()[-1][0].bg != overlay


class TestPaletteArgsMode:
    def _checkout_item(self, fetch) -> PaletteItem:
        return PaletteItem(
            "checkout",
            "Checkout branch",
            args=PaletteArgs(label="<branch>", fetch=fetch),
        )

    def test_no_space_keeps_template_filter(self):
        calls: list[str] = []
        items = [
            PaletteItem("stash", "Focus stash"),
            self._checkout_item(lambda rest: calls.append(rest) or ["dev"]),
        ]
        palette = CommandPalette(items=items, list_slots=10)
        palette.open()
        _type(palette, "sta")
        assert _ids(palette) == ["stash"]
        assert palette._arg_mode is None
        assert calls == []

    def test_prefix_space_switches_to_fetch_candidates(self):
        calls: list[str] = []
        items = [
            self._checkout_item(lambda rest: calls.append(rest) or ["dev", "main"])
        ]
        palette = CommandPalette(items=items, list_slots=10)
        palette.open()
        _type(palette, "checkout ")
        assert palette._arg_mode == "checkout"
        assert calls == [""]
        assert _ids(palette) == ["checkout dev", "checkout main"]

    def test_space_then_fragment_passes_rest_unstripped(self):
        calls: list[str] = []
        items = [self._checkout_item(lambda rest: calls.append(rest) or [])]
        palette = CommandPalette(items=items, list_slots=10)
        palette.open()
        _type(palette, "checkout  x")
        assert calls[-1] == " x"

    def test_fetch_lazy_per_keystroke(self):
        calls: list[str] = []
        items = [self._checkout_item(lambda rest: calls.append(rest) or ["ab"])]
        palette = CommandPalette(items=items, list_slots=10)
        palette.open()
        _type(palette, "checkout a")
        assert calls == ["", "a"]

    def test_max_matched_slices_fetch_results(self):
        values = [f"b{i}" for i in range(MAX_MATCHED + 10)]
        items = [self._checkout_item(lambda rest: values)]
        palette = CommandPalette(items=items, list_slots=10)
        palette.open()
        _type(palette, "checkout ")
        assert len(palette._matched) == MAX_MATCHED

    def test_fetch_exception_yields_empty_candidates(self):
        def boom(_rest: str) -> list[str]:
            raise RuntimeError("boom")

        items = [self._checkout_item(boom)]
        palette = CommandPalette(items=items, list_slots=10)
        palette.open()
        _type(palette, "checkout ")
        assert palette._arg_mode == "checkout"
        assert palette._matched == []

    def test_submit_arg_mode_selected_zero_uses_input(self):
        executed: list[str] = []
        items = [
            self._checkout_item(lambda rest: ["develop", "dev"]),
        ]
        palette = CommandPalette(
            items=items,
            list_slots=10,
            on_execute=lambda item: executed.append(item),
        )
        palette.open()
        _type(palette, "checkout dev")
        assert palette._selected == 0
        palette.handle_key(keys.KEY_ENTER)
        assert executed == ["checkout dev"]

    def test_submit_arg_mode_selected_positive_uses_matched(self):
        executed: list[str] = []
        items = [self._checkout_item(lambda rest: ["develop", "dev"])]
        palette = CommandPalette(
            items=items,
            list_slots=10,
            on_execute=lambda item: executed.append(item),
        )
        palette.open()
        _type(palette, "checkout d")
        palette.handle_key(keys.KEY_DOWN)
        assert palette._selected == 1
        palette.handle_key(keys.KEY_ENTER)
        assert executed == ["checkout dev"]

    def test_submit_template_mode_sta_still_picks_stash(self):
        executed: list[str] = []
        items = [
            PaletteItem("status", "Status"),
            PaletteItem("stash", "Stash"),
            self._checkout_item(lambda rest: ["dev"]),
        ]
        palette = CommandPalette(
            items=items,
            list_slots=10,
            on_execute=lambda item: executed.append(item),
        )
        palette.open()
        _type(palette, "stas")
        assert palette._arg_mode is None
        assert _ids(palette) == ["stash"]
        palette.handle_key(keys.KEY_ENTER)
        assert executed == ["stash"]

    def test_coerce_three_tuple_passes_args(self):
        args = PaletteArgs(label="<x>", fetch=lambda rest: ["a"])
        palette = CommandPalette(items=[("checkout", "Checkout", args)], list_slots=10)
        palette.open()
        assert palette._items[0].args is args
        _type(palette, "checkout ")
        assert _ids(palette) == ["checkout a"]

    def test_refresh_candidates_noop_when_inactive(self):
        source = ["dev"]
        items = [
            PaletteItem(
                "checkout",
                args=PaletteArgs(label="<b>", fetch=lambda rest: list(source)),
            )
        ]
        palette = CommandPalette(items=items, list_slots=10)
        with patch("pigit.termui.widgets.command_palette.request_render") as render:
            palette.refresh_candidates()
        assert not palette.is_active
        assert palette._matched == []
        render.assert_not_called()

    def test_refresh_candidates_recomputes_and_renders(self):
        source = ["old"]
        items = [
            PaletteItem(
                "checkout",
                args=PaletteArgs(label="<b>", fetch=lambda rest: list(source)),
            )
        ]
        palette = CommandPalette(items=items, list_slots=10)
        palette.open()
        _type(palette, "checkout ")
        assert _ids(palette) == ["checkout old"]
        source[:] = ["new"]
        with patch("pigit.termui.widgets.command_palette.request_render") as render:
            palette.refresh_candidates()
        assert _ids(palette) == ["checkout new"]
        render.assert_called_once()

    def test_tab_fills_selected_candidate_id(self):
        items = [self._checkout_item(lambda rest: ["develop", "dev"])]
        palette = CommandPalette(items=items, list_slots=10)
        palette.open()
        _type(palette, "checkout d")
        palette.handle_key(keys.KEY_DOWN)
        assert palette._selected == 1
        palette.handle_key(keys.KEY_TAB)
        assert palette.is_active
        assert palette._input_line.value == "checkout dev"
        assert palette._selected == 0
        assert "checkout dev" in _ids(palette)

    def test_tab_noop_when_no_candidates(self):
        items = [self._checkout_item(lambda rest: [])]
        palette = CommandPalette(items=items, list_slots=10)
        palette.open()
        _type(palette, "checkout ")
        assert palette._matched == []
        palette.handle_key(keys.KEY_TAB)
        assert palette._input_line.value == "checkout "
        assert palette.is_active

    def test_tab_completes_template_command_id(self):
        items = [
            PaletteItem("status", "Status"),
            PaletteItem("stash", "Stash"),
        ]
        palette = CommandPalette(items=items, list_slots=10)
        palette.open()
        _type(palette, "stas")
        assert _ids(palette) == ["stash"]
        palette.handle_key(keys.KEY_TAB)
        assert palette._input_line.value == "stash"
        assert palette.is_active
        assert _ids(palette) == ["stash"]
