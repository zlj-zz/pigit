"""
Module: pigit/app_search_filter.py
Description: Search/filter controller for TUI panels (composition over mixin).
Author: Zev
Date: 2026-05-26
"""

from __future__ import annotations

from collections.abc import Callable

from pigit.termui import keys, palette
from pigit.app_theme import THEME


class SearchFilter:
    """Encapsulates search/filter UI state and behavior for a panel.

    The panel provides an ``apply_filter`` callback that is invoked whenever
    the query changes. The panel is responsible for reading ``self.query`` and
    updating ``self.map`` inside that callback.
    """

    def __init__(self, apply_filter: Callable[[], None]) -> None:
        self.query: str = ""
        self.active: bool = False
        self.map: list[int] = []
        self._apply = apply_filter

    def enter(self) -> None:
        """Activate search mode with empty query."""
        self.active = True
        self.query = ""
        self._apply()

    def exit(self) -> None:
        """Deactivate search mode and clear query."""
        self.active = False
        self.query = ""
        self._apply()

    def source_index(self, visible_idx: int) -> int:
        """Map a visible (filtered) index back to the source index."""
        if self.map and visible_idx < len(self.map):
            return self.map[visible_idx]
        return visible_idx

    def handle_key(self, key: str) -> bool:
        """Handle search-related key input.

        Returns ``True`` if the key was consumed.
        """
        if self.active:
            if key == keys.KEY_ESC:
                self.exit()
                return True
            if key == keys.KEY_ENTER:
                self.active = False
                return True
            if key == keys.KEY_BACKSPACE:
                self.query = self.query[:-1]
                self._apply()
                return True
            if len(key) == 1 and key.isprintable():
                self.query += key
                self._apply()
                return True
            return False

        if key == "/":
            self.enter()
            return True

        return False

    def render_bar(self, surface) -> None:
        """Draw search/filter status bar at the bottom of the surface."""
        if not self.query and not self.active:
            return
        row = surface.height - 1
        if row < 0:
            return
        if self.active:
            text = f"/{self.query}"
            fg = THEME.fg_branch_name
            flags = palette.STYLE_BOLD
        else:
            text = f"filter: {self.query}"
            fg = THEME.fg_muted
            flags = 0
        text = text.ljust(surface.width)[: surface.width]
        surface.draw_text_rgb(row, 0, text, fg=fg, style_flags=flags)
