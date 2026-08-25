"""
Module: pigit/termui/widgets/footer.py
Description: Generic footer bar with context text and shortcut hints.
Author: Zev
Date: 2026-08-19
"""

from __future__ import annotations

from collections.abc import Callable

from .. import palette
from ..component import Component
from ..surface import Surface
from ..theme import get_theme
from ..wcwidth_table import truncate_by_width, wcswidth


class Footer(Component):
    """Bottom bar: current item context + shortcut hints.

    Renders a separator row (when height >= 2) and a content row with
    context text on the left and key/description pairs on the right.
    Keys use fg_primary + bold; descriptions use fg_muted.
    """

    def __init__(self, *, id: str | None = None) -> None:
        super().__init__(id=id)
        self._context_text = ""
        self._global_help: list[tuple[str, str]] = []
        self._help_provider: Callable[[], list[tuple[str, str]]] | None = None

    def set_context(self, item_name: str = "") -> None:
        """Set or clear the left-side context label.

        Args:
            item_name: Item name to display; empty string clears the label.
        """
        self._context_text = f"\u2192 {item_name}" if item_name else ""

    def set_global_help(self, pairs: list[tuple[str, str]]) -> None:
        """Replace globally appended help entries (deduplicated by key).

        Args:
            pairs: List of (key, description) tuples.
        """
        self._global_help = list(pairs)

    def set_help_provider(
        self, provider: Callable[[], list[tuple[str, str]]] | None
    ) -> None:
        """Register a callable that supplies panel-specific help each render.

        Args:
            provider: Callable returning (key, description) pairs, or None.
        """
        self._help_provider = provider

    def paint(self, surface: Surface) -> None:
        """Separator row, key bold, desc muted, ellipsis. Same layout as AppFooter."""
        theme = get_theme()
        w = surface.width
        h = surface.height
        if w <= 0:
            return

        if h >= 2:
            surface.draw_text_rgb(0, 0, "\u2500" * w, fg=theme.fg_dim)
            self._draw_footer_content(surface, 1, w, theme)
        else:
            surface.draw_text_rgb(0, 0, "\u2500" * w, fg=theme.fg_dim)
            self._draw_footer_content(surface, 0, w, theme)

    def _draw_footer_content(
        self,
        surface: Surface,
        row: int,
        w: int,
        theme,
    ) -> None:
        """Draw footer text content at the given row.

        Keys are rendered bright (fg_primary + bold), descriptions dim (fg_muted).
        Panel help is pulled from the registered provider each render cycle;
        global help is appended and deduplicated by key.
        """
        left_text = self._context_text
        left_w = wcswidth(left_text)
        x = 0

        if left_text:
            surface.draw_text_rgb(row, x, left_text, fg=theme.fg_primary)
            x += left_w + 2

        panel_help = self._help_provider() if self._help_provider else []
        seen = {key for key, _ in panel_help}
        help_pairs = list(panel_help)
        for key, desc in self._global_help:
            if key not in seen:
                help_pairs.append((key, desc))

        for key, desc in help_pairs:
            pair_text = f"{key} {desc}"
            pair_w = wcswidth(pair_text)
            if x + pair_w > w:
                avail = max(0, w - x - 1)
                if avail > 0:
                    surface.draw_text_rgb(
                        row,
                        x,
                        truncate_by_width(pair_text, avail) + "\u2026",
                        fg=theme.fg_muted,
                    )
                break

            key_w = wcswidth(key)
            surface.draw_text_rgb(
                row,
                x,
                key,
                fg=theme.fg_primary,
                style_flags=palette.STYLE_BOLD,
            )
            x += key_w

            rest = f" {desc}  "
            surface.draw_text_rgb(row, x, rest, fg=theme.fg_muted)
            x += wcswidth(rest)
