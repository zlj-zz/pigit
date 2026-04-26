# -*- coding: utf-8 -*-
"""
Module: pigit/app_chrome.py
Description: Application chrome components (header, footer, peek label).
Author: Zev
Date: 2026-04-23
"""

from __future__ import annotations

import time
from typing import Callable, Optional

from pigit.termui import Component
from pigit.termui.wcwidth_table import truncate_by_width, wcswidth
from pigit.termui._surface import _DEFAULT_BG

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
            surface.fill_rect_rgb(0, 0, w, 1, _DEFAULT_BG)
            surface.draw_text_rgb(
                0, 0, "\u2500" * w, fg=self._theme.fg_dim, bg=_DEFAULT_BG
            )
            # Row 1: content
            self._draw_footer_content(surface, 1, w)
        else:
            # Single-row fallback: border line overlaid with content
            surface.fill_rect_rgb(0, 0, w, 1, _DEFAULT_BG)
            surface.draw_text_rgb(
                0, 0, "\u2500" * w, fg=self._theme.fg_dim, bg=_DEFAULT_BG
            )
            self._draw_footer_content(surface, 0, w)

    def _draw_footer_content(self, surface, row: int, w: int) -> None:
        """Draw footer text content at the given row.

        Keys are rendered bright (fg_primary + bold), descriptions dim (fg_muted).
        Panel help is pulled from the registered provider each render cycle;
        global help is appended and deduplicated by key.
        """
        surface.fill_rect_rgb(row, 0, w, 1, _DEFAULT_BG)

        left_text = self._context_text
        left_w = wcswidth(left_text)
        x = 0

        if left_text:
            surface.draw_text_rgb(
                row, x, left_text, fg=self._theme.fg_primary, bg=_DEFAULT_BG
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
                        bg=_DEFAULT_BG,
                    )
                break

            # Draw key bright + bold
            key_w = wcswidth(key)
            surface.draw_text_rgb(
                row, x, key, fg=self._theme.fg_primary, bg=_DEFAULT_BG, bold=True
            )
            x += key_w

            # Space + description dim
            rest = f" {desc}  "
            surface.draw_text_rgb(row, x, rest, fg=self._theme.fg_muted, bg=_DEFAULT_BG)
            x += wcswidth(rest)


class PeekLabel:
    """Transient tab-switch feedback rendered into body surface.

    Not a Component — managed directly by PigitApplication.
    """

    def __init__(self) -> None:
        self._label: Optional[str] = None
        self._peek_until: float = 0.0

    def show(self, label: str, duration: float = 0.5) -> None:
        """Trigger a peek label display."""
        self._label = label
        self._peek_until = time.monotonic() + duration

    def is_visible(self) -> bool:
        """Check if the peek label should still be rendered."""
        if self._label is None:
            return False
        if time.monotonic() > self._peek_until:
            self._label = None
            return False
        return True

    def render(self, surface, theme: FlatTheme) -> None:
        """Render the peek label centered on the given surface."""
        if not self.is_visible():
            return
        if not self._label:
            return

        w, h = surface.width, surface.height
        if w < 10 or h < 3:
            return

        label = self._label
        label_w = wcswidth(label)

        # Box dimensions
        box_w = min(w - 4, label_w + 6)
        box_h = min(h - 2, 3)
        box_x = (w - box_w) // 2
        box_y = (h - box_h) // 2

        # Fill background
        surface.fill_rect_rgb(box_y, box_x, box_w, box_h, theme.bg_active)

        # Center text
        text_x = box_x + (box_w - label_w) // 2
        text_y = box_y + box_h // 2
        surface.draw_text_rgb(
            text_y,
            text_x,
            label,
            fg=theme.fg_primary,
            bg=theme.bg_active,
            bold=True,
        )
