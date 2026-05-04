# -*- coding: utf-8 -*-
"""
Module: pigit/app_chrome.py
Description: Application chrome components (header, footer).
Author: Zev
Date: 2026-04-23
"""

from __future__ import annotations

from typing import Callable, Optional

from pigit.termui import Component, palette
from pigit.termui.wcwidth_table import truncate_by_width, wcswidth

from .app_theme import FlatTheme


class AppFooter(Component):
    """Bottom chrome bar: current item context + shortcut hints."""

    def __init__(self, theme: FlatTheme) -> None:
        super().__init__()
        self._theme = theme
        self._context_text = ""
        self._global_help: list[tuple[str, str]] = []
        self._help_provider: Optional[Callable[[], list[tuple[str, str]]]] = None

    def set_context(self, item_name: str = "") -> None:
        self._context_text = f"\u2192 {item_name}" if item_name else ""

    def set_global_help(self, pairs: list[tuple[str, str]]) -> None:
        self._global_help = list(pairs)

    def set_help_provider(
        self, provider: Optional[Callable[[], list[tuple[str, str]]]]
    ) -> None:
        self._help_provider = provider

    def _render_surface(self, surface) -> None:
        w = surface.width
        h = surface.height
        if w <= 0:
            return

        if h >= 2:
            # Two-row footer: dedicated separator line + content row
            # Row 0: separator
            surface.fill_rect_rgb(0, 0, w, 1, palette.DEFAULT_BG)
            surface.draw_text_rgb(
                0, 0, "\u2500" * w, fg=self._theme.fg_dim, bg=palette.DEFAULT_BG
            )
            # Row 1: content
            self._draw_footer_content(surface, 1, w)
        else:
            # Single-row fallback: border line overlaid with content
            surface.fill_rect_rgb(0, 0, w, 1, palette.DEFAULT_BG)
            surface.draw_text_rgb(
                0, 0, "\u2500" * w, fg=self._theme.fg_dim, bg=palette.DEFAULT_BG
            )
            self._draw_footer_content(surface, 0, w)

    def _draw_footer_content(self, surface, row: int, w: int) -> None:
        """Draw footer text content at the given row.

        Keys are rendered bright (fg_primary + bold), descriptions dim (fg_muted).
        Panel help is pulled from the registered provider each render cycle;
        global help is appended and deduplicated by key.
        """
        surface.fill_rect_rgb(row, 0, w, 1, palette.DEFAULT_BG)

        left_text = self._context_text
        left_w = wcswidth(left_text)
        x = 0

        if left_text:
            surface.draw_text_rgb(
                row, x, left_text, fg=self._theme.fg_primary, bg=palette.DEFAULT_BG
            )
            x += left_w + 2

        # Pull panel help from provider and merge with global help
        panel_help = self._help_provider() if self._help_provider else []
        seen = {key for key, _ in panel_help}
        help_pairs = list(panel_help)
        for key, desc in self._global_help:
            if key not in seen:
                help_pairs.append((key, desc))

        # Draw help pairs: key bright, description dim
        for key, desc in help_pairs:
            # Each pair: "key desc"  +  two spaces before next pair
            pair_text = f"{key} {desc}"
            pair_w = wcswidth(pair_text)
            if x + pair_w > w:
                # Not enough space — truncate with ellipsis
                avail = max(0, w - x - 1)
                if avail > 0:
                    surface.draw_text_rgb(
                        row,
                        x,
                        truncate_by_width(pair_text, avail) + "\u2026",
                        fg=self._theme.fg_muted,
                        bg=palette.DEFAULT_BG,
                    )
                break

            # Draw key bright + bold
            key_w = wcswidth(key)
            surface.draw_text_rgb(
                row,
                x,
                key,
                fg=self._theme.fg_primary,
                bg=palette.DEFAULT_BG,
                style_flags=palette.STYLE_BOLD,
            )
            x += key_w

            # Space + description dim
            rest = f" {desc}  "
            surface.draw_text_rgb(
                row, x, rest, fg=self._theme.fg_muted, bg=palette.DEFAULT_BG
            )
            x += wcswidth(rest)
