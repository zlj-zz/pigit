"""
Module: pigit/app_chrome.py
Description: Application chrome components (header, footer).
Author: Zev
Date: 2026-04-23
"""

from __future__ import annotations

from collections.abc import Callable

from pigit.termui import ActionEventType, by_id, Component, palette, resolve_presented
from pigit.termui.containers import TabView
from pigit.termui.wcwidth_table import truncate_by_width, wcswidth

from .app_theme import FlatTheme


class AppFooter(Component):
    """Bottom chrome bar: current item context + shortcut hints."""

    def __init__(
        self,
        theme: FlatTheme,
        id: str | None = None,
    ) -> None:
        super().__init__(id=id)
        self._theme = theme
        self._context_text = ""
        self._global_help: list[tuple[str, str]] = []
        self._help_provider: Callable[[], list[tuple[str, str]]] | None = None

    def activate(self) -> None:
        super().activate()
        self.subscribe(ActionEventType.selection_changed, self._sync_help)
        self.subscribe(ActionEventType.mode_changed, self._sync_help)

    def _sync_help(self, *, active: Component | None = None, **_) -> bool:
        if active is None:
            tab_view = by_id("tab_view", TabView)
            active = (
                resolve_presented(tab_view.active) if tab_view is not None else None
            )
        provider = getattr(active, "get_help_entries", None) if active else None
        self.set_help_provider(provider)
        return True

    def set_context(self, item_name: str = "") -> None:
        self._context_text = f"\u2192 {item_name}" if item_name else ""

    def set_global_help(self, pairs: list[tuple[str, str]]) -> None:
        self._global_help = list(pairs)

    def set_help_provider(
        self, provider: Callable[[], list[tuple[str, str]]] | None
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
            surface.draw_text_rgb(0, 0, "\u2500" * w, fg=self._theme.fg_dim)
            # Row 1: content
            self._draw_footer_content(surface, 1, w)
        else:
            # Single-row fallback: border line overlaid with content
            surface.draw_text_rgb(0, 0, "\u2500" * w, fg=self._theme.fg_dim)
            self._draw_footer_content(surface, 0, w)

    def _draw_footer_content(self, surface, row: int, w: int) -> None:
        """Draw footer text content at the given row.

        Keys are rendered bright (fg_primary + bold), descriptions dim (fg_muted).
        Panel help is pulled from the registered provider each render cycle;
        global help is appended and deduplicated by key.
        """
        left_text = self._context_text
        left_w = wcswidth(left_text)
        x = 0

        if left_text:
            surface.draw_text_rgb(row, x, left_text, fg=self._theme.fg_primary)
            x += left_w + 2

        # Pull panel help from provider, then append global help
        # (Inspector / Palette / Quit). Panels control which entries appear.
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
                    )
                break

            # Draw key bright + bold
            key_w = wcswidth(key)
            surface.draw_text_rgb(
                row,
                x,
                key,
                fg=self._theme.fg_primary,
                style_flags=palette.STYLE_BOLD,
            )
            x += key_w

            # Space + description dim
            rest = f" {desc}  "
            surface.draw_text_rgb(row, x, rest, fg=self._theme.fg_muted)
            x += wcswidth(rest)
