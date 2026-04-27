# -*- coding: utf-8 -*-
"""
Module: pigit/app_palette.py
Description: Command palette with InputLine and candidate list.
Author: Zev
Date: 2026-04-23
"""

from __future__ import annotations

from typing import Callable, Optional

from pigit.termui import Component, keys
from pigit.termui.types import OverlayDispatchResult
from pigit.termui.wcwidth_table import truncate_by_width, wcswidth

from .app_theme import THEME


# Default command palette commands
DEFAULT_COMMANDS: list[str] = [
    "status",
    "branch",
    "commit",
    "diff",
    "log",
    "stash",
    "pull",
    "push",
    "fetch",
    "checkout",
    "merge",
    "rebase",
    "reset",
    "clean",
    "tag",
    "config",
    "help",
    "quit",
]


class CommandPalette(Component):
    """Bottom-anchored command palette using InputLine + candidate list."""

    def __init__(
        self,
        on_execute: Optional[Callable[[str], None]] = None,
        on_dismiss: Optional[Callable[[], None]] = None,
        commands: Optional[list[str]] = None,
        x: int = 1,
        y: int = 1,
        size: Optional[tuple[int, int]] = None,
    ) -> None:
        super().__init__(x, y, size)
        self._on_execute = on_execute
        self._on_dismiss = on_dismiss
        self._commands = commands or list(DEFAULT_COMMANDS)
        self._value = ""
        self._cursor = 0
        self._candidates: list[str] = []
        self._selected = 0
        self._active = False

    @property
    def is_active(self) -> bool:
        return self._active

    def open(self) -> None:
        """Activate the palette."""
        self._active = True
        self._value = ""
        self._cursor = 0
        self._candidates = []
        self._selected = 0

    def close(self) -> None:
        """Deactivate the palette."""
        self._active = False
        self._value = ""
        self._cursor = 0
        self._candidates = []
        self._selected = 0
        if self._on_dismiss is not None:
            self._on_dismiss()

    def dispatch_overlay_key(self, key: str) -> OverlayDispatchResult:
        """Route key to palette while active on a sheet layer."""
        self.on_key(key)
        return OverlayDispatchResult.HANDLED_EXPLICIT

    def on_key(self, key: str) -> None:
        """Process keyboard input."""
        if key == keys.KEY_ESC:
            self.close()
            return
        if key == keys.KEY_ENTER:
            if self._candidates and self._selected < len(self._candidates):
                cmd = self._candidates[self._selected]
            else:
                cmd = self._value.strip()
            if cmd and self._on_execute:
                self._on_execute(cmd)
            self.close()
            return
        if key == keys.KEY_UP:
            if self._candidates:
                self._selected = max(0, self._selected - 1)
            return
        if key == keys.KEY_DOWN:
            if self._candidates:
                self._selected = min(len(self._candidates) - 1, self._selected + 1)
            return
        if key == keys.KEY_BACKSPACE:
            if self._cursor > 0:
                self._value = (
                    self._value[: self._cursor - 1] + self._value[self._cursor :]
                )
                self._cursor -= 1
                self._update_candidates()
            return
        if key == keys.KEY_LEFT:
            self._cursor = max(0, self._cursor - 1)
            return
        if key == keys.KEY_RIGHT:
            self._cursor = min(len(self._value), self._cursor + 1)
            return
        if key == keys.KEY_HOME:
            self._cursor = 0
            return
        if key == keys.KEY_END:
            self._cursor = len(self._value)
            return
        if key == keys.KEY_DELETE:
            if self._cursor < len(self._value):
                self._value = (
                    self._value[: self._cursor] + self._value[self._cursor + 1 :]
                )
                self._update_candidates()
            return
        if len(key) == 1 and key.isprintable() and ord(key) >= 32:
            self._value = (
                self._value[: self._cursor] + key + self._value[self._cursor :]
            )
            self._cursor += 1
            self._update_candidates()

        # Defensive clamp: ensure cursor invariant even if future key
        # handlers or external mutation leave _cursor out of bounds.
        self._cursor = max(0, min(len(self._value), self._cursor))

    def _update_candidates(self) -> None:
        """Update candidate list based on current input."""
        value = self._value.strip().lower()
        if not value:
            self._candidates = []
            self._selected = 0
            return
        self._candidates = [cmd for cmd in self._commands if value in cmd.lower()][:10]
        self._selected = 0

    def _render_surface(self, surface) -> None:
        if not self._active:
            return
        w = surface.width
        h = surface.height
        if w <= 0 or h <= 0:
            return

        _PALETTE_BG = (45, 45, 50)

        # Background
        surface.fill_rect_rgb(0, 0, w, h, _PALETTE_BG)

        # Top border
        surface.draw_text_rgb(0, 0, "─" * w, fg=THEME.fg_dim, bg=_PALETTE_BG)

        # Input line at bottom
        input_row = h - 1
        prompt = "> "
        core = f"{prompt}{self._value}"
        cursor_abs = len(prompt) + self._cursor

        # Draw input text
        if wcswidth(core) > w:
            core = truncate_by_width(core, w - 1) + "…"
        surface.draw_text_rgb(input_row, 0, core, fg=THEME.fg_primary, bg=_PALETTE_BG)

        # Block cursor
        if cursor_abs < w:
            ch = self._value[self._cursor] if self._cursor < len(self._value) else " "
            surface.draw_text_rgb(
                input_row, cursor_abs, ch, fg=_PALETTE_BG, bg=THEME.fg_primary
            )

        # Candidate list above input
        if self._candidates:
            max_candidates = min(len(self._candidates), h - 2)
            start_row = input_row - max_candidates
            for i, candidate in enumerate(self._candidates[:max_candidates]):
                row = start_row + i
                if row < 0:
                    continue
                is_selected = i == self._selected
                fg = THEME.fg_primary if is_selected else THEME.fg_muted
                bg = THEME.bg_active if is_selected else _PALETTE_BG
                text = f"  {candidate}"
                if wcswidth(text) > w:
                    text = truncate_by_width(text, w - 1) + "…"
                surface.draw_text_rgb(row, 0, text, fg=fg, bg=bg)
