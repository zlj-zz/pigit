"""
Module: pigit/termui/widgets/command_palette.py
Description: Generic bottom-anchored command palette with filterable item list.
Author: Zev
Date: 2026-08-20
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from .. import keys
from ..theme import get_theme
from ..component import Component
from ..types import OverlayDispatchResult
from ..wcwidth_table import truncate_by_width, wcswidth
from .input_line import InputLine

MAX_CANDIDATES = 10


def _default_match(needle: str, item: str) -> bool:
    """Return True when *needle* is a case-insensitive substring of *item*."""
    return needle.lower() in item.lower()


class CommandPalette(Component):
    """Bottom-anchored palette using InputLine and a filterable candidate list."""

    def __init__(
        self,
        *,
        items: Sequence[str],
        on_execute: Callable[[str], None] | None = None,
        on_dismiss: Callable[[], None] | None = None,
        match: Callable[[str, str], bool] | None = None,
        id: str | None = None,
        x: int = 1,
        y: int = 1,
        size: tuple[int, int] | None = None,
    ) -> None:
        super().__init__(x, y, size, id=id)
        self._items = list(items)
        self._on_execute = on_execute
        self._on_dismiss = on_dismiss
        self._match = match or _default_match
        self._input_line = InputLine(
            prompt="> ",
            on_value_changed=self._on_input_changed,
            allow_newline=False,
        )
        self._candidates: list[str] = []
        self._selected = 0
        self._active = False

    @property
    def is_active(self) -> bool:
        """Return True while the palette is open."""
        return self._active

    def open(self) -> None:
        """Activate the palette and reset input state."""
        self._active = True
        self._input_line.clear()
        self._candidates = []
        self._selected = 0

    def close(self) -> None:
        """Deactivate the palette and invoke the dismiss callback."""
        self._active = False
        self._input_line.clear()
        self._candidates = []
        self._selected = 0
        if self._on_dismiss is not None:
            self._on_dismiss()

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
                if self._candidates and self._selected < len(self._candidates):
                    value = self._candidates[self._selected]
                else:
                    value = self._input_line.value.strip()
                if value and self._on_execute:
                    self._on_execute(value)
                self.close()
            case keys.KEY_UP:
                if self._candidates:
                    self._selected = max(0, self._selected - 1)
            case keys.KEY_DOWN:
                if self._candidates:
                    self._selected = min(len(self._candidates) - 1, self._selected + 1)
            case _:
                self._input_line.handle_key(key)
        return True

    def _on_input_changed(self, value: str) -> None:
        """Callback fired by InputLine when value changes."""
        self._update_candidates()

    def _update_candidates(self) -> None:
        """Update candidate list based on current input."""
        needle = self._input_line.value.strip()
        if not needle:
            self._candidates = []
            self._selected = 0
            return
        self._candidates = [item for item in self._items if self._match(needle, item)][
            :MAX_CANDIDATES
        ]
        self._selected = 0

    def _render_surface(self, surface) -> None:
        if not self._active:
            return
        theme = get_theme()
        w = surface.width
        h = surface.height
        if w <= 0 or h <= 0:
            return

        surface.fill_rect_rgb(0, 0, w, h, theme.bg_overlay)
        surface.draw_text_rgb(0, 0, "─" * w, fg=theme.fg_dim, bg=theme.bg_overlay)

        input_row = h - 1
        prompt = self._input_line.prompt
        core = f"{prompt}{self._input_line.value}"
        cursor_abs = len(prompt) + self._input_line.cursor

        if wcswidth(core) > w:
            core = truncate_by_width(core, w - 1) + "…"
        surface.draw_text_rgb(
            input_row, 0, core, fg=theme.fg_primary, bg=theme.bg_overlay
        )

        if cursor_abs < w:
            ch = (
                self._input_line.value[self._input_line.cursor]
                if self._input_line.cursor < len(self._input_line.value)
                else " "
            )
            surface.draw_text_rgb(
                input_row, cursor_abs, ch, fg=theme.bg_overlay, bg=theme.fg_primary
            )

        if self._candidates:
            max_candidates = min(len(self._candidates), h - 2)
            start_row = input_row - max_candidates
            for i, candidate in enumerate(self._candidates[:max_candidates]):
                row = start_row + i
                if row < 0:
                    continue
                is_selected = i == self._selected
                fg = theme.fg_primary if is_selected else theme.fg_muted
                bg = theme.bg_active if is_selected else theme.bg_overlay
                text = f"  {candidate}"
                if wcswidth(text) > w:
                    text = truncate_by_width(text, w - 1) + "…"
                surface.draw_text_rgb(row, 0, text, fg=fg, bg=bg)
