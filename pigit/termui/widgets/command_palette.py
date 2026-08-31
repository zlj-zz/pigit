"""
Module: pigit/termui/widgets/command_palette.py
Description: Generic bottom-anchored command palette with filterable item list.
Author: Zev
Date: 2026-08-20
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import NamedTuple

from .. import keys, palette
from .._runtime_context import request_render
from ..theme import get_theme
from ..component import Component
from ..surface import Surface
from ..types import OverlayDispatchResult
from ..wcwidth_table import truncate_by_width, wcswidth
from .input_line import InputLine

MAX_MATCHED = 32
MIN_LIST_SLOTS = 3
MAX_LIST_SLOTS = 10
_HINT = "↑↓ enter tab · esc"
_HINT_GAP = 2
# Child rows below Sheet border: list/input rule + prompt.
_SHEET_CHROME_ROWS = 2


@dataclass(frozen=True)
class PaletteArgs:
    """Argument-completion descriptor for a parameterized palette command.

    ``fetch`` returns candidate entries: a plain ``str`` (used as both value
    and display) or a ``(value, display)`` tuple whose display string is
    shown on the row while the id keeps the clean, parseable value.
    """

    label: str
    fetch: Callable[[str], list[str | tuple[str, str]]]


class PaletteItem(NamedTuple):
    """One palette entry: executable id plus short description."""

    id: str
    desc: str = ""
    args: PaletteArgs | None = None


def list_slots_for_term(term_h: int) -> int:
    """Return how many list rows the palette should use for *term_h*.

    Targets about one-third of the terminal for the whole sheet (border +
    list + rule + input), clamped so small terminals stay usable.
    """
    sheet_h = min(
        max(term_h // 3, MIN_LIST_SLOTS + 3), max(term_h // 2, 1), MAX_LIST_SLOTS + 3
    )
    return max(MIN_LIST_SLOTS, min(MAX_LIST_SLOTS, sheet_h - 3))


def _coerce_items(
    items: Sequence[str | tuple | PaletteItem],
) -> list[PaletteItem]:
    """Normalize legacy strings and tuples into PaletteItem (args optional)."""
    out: list[PaletteItem] = []
    for item in items:
        if isinstance(item, PaletteItem):
            out.append(item)
        elif isinstance(item, tuple):
            if len(item) >= 3:
                out.append(PaletteItem(item[0], item[1], item[2]))
            else:
                out.append(PaletteItem(item[0], item[1] if len(item) > 1 else ""))
        else:
            out.append(PaletteItem(str(item)))
    return out


def _default_match(needle: str, item: PaletteItem) -> bool:
    """Return True when *needle* matches id or description (case-insensitive)."""
    n = needle.lower()
    return n in item.id.lower() or n in item.desc.lower()


class CommandPalette(Component):
    """Bottom-anchored palette using InputLine and a filterable candidate list."""

    def __init__(
        self,
        *,
        items: Sequence[str | tuple | PaletteItem],
        on_execute: Callable[[str], None] | None = None,
        on_dismiss: Callable[[], None] | None = None,
        match: Callable[[str, PaletteItem], bool] | None = None,
        list_slots: int = MAX_LIST_SLOTS,
        id: str | None = None,
        x: int = 1,
        y: int = 1,
        size: tuple[int, int] | None = None,
    ) -> None:
        super().__init__(x, y, size, id=id)
        self._items = _coerce_items(items)
        self._on_execute = on_execute
        self._on_dismiss = on_dismiss
        self._match = match or _default_match
        self._list_slots = max(MIN_LIST_SLOTS, list_slots)
        self._input_line = InputLine(
            prompt="> ",
            on_value_changed=self._on_input_changed,
            allow_newline=False,
        )
        self._matched: list[PaletteItem] = []
        self._selected = 0  # index into _matched
        self._scroll = 0  # window start into _matched
        self._active = False
        self._arg_mode: str | None = None

    @property
    def is_active(self) -> bool:
        """Return True while the palette is open."""
        return self._active

    @property
    def _candidates(self) -> list[PaletteItem]:
        """Visible rows in the current scroll window."""
        visible, _below, _above = self._visible_window()
        return visible

    def preferred_sheet_height(self, term_h: int | None = None) -> int:
        """Sheet rows: list band + rule + prompt (plus Sheet edge rule outside).

        Uses the current ``_list_slots`` budget from the constructor or
        ``open(list_slots=...)``. ``term_h`` is accepted for the sheet-height
        protocol only and must not rewrite that budget.
        """
        _ = term_h
        list_rows = self._list_rows_for_height()
        return list_rows + 1 + _SHEET_CHROME_ROWS

    def open(
        self,
        *,
        items: Sequence[str | tuple | PaletteItem] | None = None,
        list_slots: int | None = None,
    ) -> None:
        """Activate the palette; optionally refresh catalog and list budget."""
        if items is not None:
            self._items = _coerce_items(items)
        if list_slots is not None:
            self._list_slots = max(MIN_LIST_SLOTS, list_slots)
        self._active = True
        self._arg_mode = None
        self._input_line.clear()
        self._update_candidates()
        self._selected = 0
        self._scroll = 0

    def close(self) -> None:
        """Close the palette and invoke the dismiss callback."""
        self._active = False
        self._arg_mode = None
        self._input_line.clear()
        self._matched = []
        self._selected = 0
        self._scroll = 0
        if self._on_dismiss is not None:
            self._on_dismiss()

    def refresh_candidates(self) -> None:
        """Recompute the matched list while open (e.g. after async data arrives)."""
        if not self._active:
            return
        self._update_candidates()
        request_render()

    def dispatch_overlay_key(self, key: str) -> OverlayDispatchResult:
        """Route key to palette while active on a sheet layer."""
        self.handle_key(key)
        return OverlayDispatchResult.HANDLED_EXPLICIT

    def handle_key(self, key: str) -> bool:
        """Process keyboard input."""
        match key:
            case keys.KEY_ESC:
                self.close()
            case keys.KEY_ENTER:
                self._submit()
            case keys.KEY_TAB:
                self._complete_selected()
            case keys.KEY_UP:
                if self._matched:
                    self._selected = max(0, self._selected - 1)
                    self._ensure_selection_visible()
            case keys.KEY_DOWN:
                if self._matched:
                    self._selected = min(len(self._matched) - 1, self._selected + 1)
                    self._ensure_selection_visible()
            case _:
                self._input_line.handle_key(key)
        return True

    def _complete_selected(self) -> None:
        """Fill the input with the selected candidate id (Tab completion)."""
        if self._matched and 0 <= self._selected < len(self._matched):
            self._input_line.set_value(self._matched[self._selected].id)
            self._update_candidates()

    def _item_slots(self) -> int:
        """How many command rows the list band may show (terminal budget)."""
        return self._list_slots

    def _list_rows_for_height(self) -> int:
        """List band height for the open catalog."""
        n = len(self._items)
        return max(1, min(n, self._item_slots())) if n else 1

    def _ensure_selection_visible(self) -> None:
        """Slide the window so ``_selected`` stays inside the visible band."""
        matched = self._matched
        slots = self._item_slots()
        if len(matched) <= slots:
            self._scroll = 0
            return
        if self._selected < self._scroll:
            self._scroll = self._selected
        elif self._selected >= self._scroll + slots:
            self._scroll = self._selected - slots + 1
        self._scroll = max(0, min(self._scroll, len(matched) - slots))

    def _visible_window(self) -> tuple[list[PaletteItem], int, int]:
        """Return (visible rows, hidden_below, hidden_above)."""
        matched = self._matched
        slots = self._item_slots()
        if not matched:
            return [], 0, 0
        if len(matched) <= slots:
            return matched, 0, 0
        self._ensure_selection_visible()
        start = self._scroll
        visible = matched[start : start + slots]
        below = len(matched) - (start + len(visible))
        return visible, below, start

    def _submit(self) -> None:
        """Execute selected or typed id, then close.

        In argument-completion mode (``_arg_mode`` set), selection 0 keeps the
        raw input so a partial token does not silently pick the first match.
        Template mode keeps the legacy ``matched[selected]`` / typed fallback.
        """
        if self._arg_mode is not None:
            if self._selected > 0 and 0 <= self._selected < len(self._matched):
                value = self._matched[self._selected].id
            else:
                value = self._input_line.value.strip()
        elif self._matched and 0 <= self._selected < len(self._matched):
            value = self._matched[self._selected].id
        else:
            value = self._input_line.value.strip()
        if value and self._on_execute is not None:
            self._on_execute(value)
        self.close()

    def _on_input_changed(self, value: str) -> None:
        """Callback fired by InputLine when value changes."""
        self._update_candidates()

    def _update_candidates(self) -> None:
        """Refresh matched catalog; switch to arg completion after a space."""
        value = self._input_line.value
        idx = value.find(" ")
        if idx < 0:
            self._arg_mode = None
            needle = value.strip()
            if not needle:
                self._matched = self._items[:MAX_MATCHED]
            else:
                self._matched = [
                    item for item in self._items if self._match(needle, item)
                ][:MAX_MATCHED]
            self._selected = 0
            self._scroll = 0
            return

        prefix = value[:idx].rstrip()
        rest = value[idx + 1 :]
        hit: PaletteItem | None = None
        for item in self._items:
            if item.args is not None and item.id.lower() == prefix.lower():
                hit = item
                break
        if hit is None or hit.args is None:
            self._arg_mode = None
            needle = value.strip()
            if not needle:
                self._matched = self._items[:MAX_MATCHED]
            else:
                self._matched = [
                    item for item in self._items if self._match(needle, item)
                ][:MAX_MATCHED]
            self._selected = 0
            self._scroll = 0
            return

        self._arg_mode = hit.id
        try:
            values = hit.args.fetch(rest)
        except Exception:
            values = []
        # A tuple carries a pretty display string (e.g. reflog rows); the id
        # stays the clean value so submit/Tab dispatch resolves exactly.
        self._matched = [
            PaletteItem(f"{hit.id} {v[0]}", v[1])
            if isinstance(v, tuple)
            else PaletteItem(f"{hit.id} {v}")
            for v in values
        ][:MAX_MATCHED]
        self._selected = 0
        self._scroll = 0

    def paint(self, surface: Surface) -> None:
        if not self._active:
            return
        theme = get_theme()
        w = surface.width
        h = surface.height
        if w <= 0 or h <= 0:
            return

        input_row = h - 1
        visible, hidden_below, hidden_above = self._visible_window()
        show_list = bool(visible)
        show_rule = show_list and h >= 3
        rule_row = input_row - 1 if show_rule else None
        list_budget = h - (2 if show_rule else 1)

        if show_list and list_budget > 0:
            draw = visible[:list_budget]
            base = (rule_row if rule_row is not None else input_row) - len(draw)
            for i, candidate in enumerate(draw):
                row = base + i
                if row < 0:
                    continue
                matched_index = self._scroll + i
                more_below = hidden_below if i == len(draw) - 1 else 0
                more_above = hidden_above if i == 0 else 0
                self._draw_candidate_row(
                    surface,
                    row,
                    w,
                    candidate,
                    matched_index == self._selected,
                    more_below=more_below,
                    more_above=more_above,
                )

        if rule_row is not None and w > 0:
            surface.draw_hline_rgb(rule_row, 0, w, fg=theme.fg_dim, bg=None)

        prompt = self._input_line.prompt
        core = f"{prompt}{self._input_line.value}"
        cursor_abs = len(prompt) + self._input_line.cursor
        hint_w = wcswidth(_HINT)
        core_budget = w
        if hint_w + _HINT_GAP < w:
            core_budget = w - hint_w - _HINT_GAP
        if wcswidth(core) > core_budget:
            core = truncate_by_width(core, max(0, core_budget - 1)) + "…"
        surface.draw_text_rgb(input_row, 0, core, fg=theme.fg_primary)
        if hint_w + _HINT_GAP < w:
            surface.draw_text_rgb(input_row, w - hint_w, _HINT, fg=theme.fg_dim)

        if cursor_abs < w and cursor_abs < core_budget:
            ch = (
                self._input_line.value[self._input_line.cursor]
                if self._input_line.cursor < len(self._input_line.value)
                else " "
            )
            surface.draw_text_rgb(
                input_row,
                cursor_abs,
                ch,
                fg=theme.bg_chrome,
                bg=theme.fg_primary,
            )

    def _draw_candidate_row(
        self,
        surface,
        row: int,
        width: int,
        item: PaletteItem,
        selected: bool,
        *,
        more_below: int = 0,
        more_above: int = 0,
    ) -> None:
        """Draw one catalog row; edge rows may show a scroll cue on the right."""
        theme = get_theme()
        bg = theme.bg_active if selected else None
        name_fg = theme.fg_primary if selected else theme.fg_muted
        name_flags = palette.STYLE_BOLD if selected else 0
        desc_fg = theme.fg_muted if selected else theme.fg_dim
        name = f"  {item.id}"
        desc = f"  {item.desc}" if item.desc else ""
        cue = ""
        if more_below:
            cue = f" ↓{more_below}"
        elif more_above:
            cue = f" ↑{more_above}"
        cue_w = wcswidth(cue)
        name_w = wcswidth(name)
        avail_for_desc = width - name_w - cue_w
        if avail_for_desc < 0:
            name = truncate_by_width(name, max(0, width - cue_w - 1)) + "…"
            name_w = wcswidth(name)
            desc = ""
            avail_for_desc = width - name_w - cue_w
        if desc and wcswidth(desc) > avail_for_desc:
            if avail_for_desc <= 1:
                desc = ""
            else:
                desc = truncate_by_width(desc, avail_for_desc - 1) + "…"
        if selected and width > 0:
            surface.fill_rect_rgb(row, 0, width, 1, bg)
        surface.draw_text_rgb(row, 0, name, fg=name_fg, bg=bg, style_flags=name_flags)
        if desc:
            surface.draw_text_rgb(row, name_w, desc, fg=desc_fg, bg=bg)
        if cue:
            surface.draw_text_rgb(row, width - cue_w, cue, fg=theme.fg_dim, bg=bg)
