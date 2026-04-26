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

from pigit.termui import Component, get_badge
from pigit.termui.wcwidth_table import truncate_by_width, wcswidth
from pigit.termui._surface import _DEFAULT_BG

from .app_theme import FlatTheme


class AppHeader(Component):
    """Top chrome bar: repo name, branch, sync status, current tab."""

    def __init__(
        self,
        theme: FlatTheme,
        repo_name: str = "",
        branch_name: str = "",
        ahead: int = 0,
        behind: int = 0,
        current_tab: str = "",
        current_tab_key: str = "",
        mode: str = "",
    ) -> None:
        super().__init__()
        self._theme = theme
        self._repo_name = repo_name
        self._branch_name = branch_name
        self._ahead = ahead
        self._behind = behind
        self._current_tab = current_tab
        self._current_tab_key = current_tab_key
        self._mode = mode

    def set_state(
        self,
        repo_name: Optional[str] = None,
        branch_name: Optional[str] = None,
        ahead: Optional[int] = None,
        behind: Optional[int] = None,
        current_tab: Optional[str] = None,
        current_tab_key: Optional[str] = None,
        mode: Optional[str] = None,
    ) -> None:
        if repo_name is not None:
            self._repo_name = repo_name
        if branch_name is not None:
            self._branch_name = branch_name
        if ahead is not None:
            self._ahead = ahead
        if behind is not None:
            self._behind = behind
        if current_tab is not None:
            self._current_tab = current_tab
        if current_tab_key is not None:
            self._current_tab_key = current_tab_key
        if mode is not None:
            self._mode = mode

    def _render_surface(self, surface) -> None:
        w = surface.width
        h = surface.height
        if w <= 0:
            return

        if h >= 2:
            # Two-row header: content + separator
            self._draw_header_content(surface, 0, w)
            surface.fill_rect_rgb(1, 0, w, 1, _DEFAULT_BG)
            surface.draw_text_rgb(
                1, 0, "\u2500" * w, fg=self._theme.fg_dim, bg=_DEFAULT_BG
            )
        else:
            self._draw_header_content(surface, 0, w)

    def _draw_header_content(self, surface, row: int, w: int) -> None:
        """Draw header text content at the given row."""
        surface.fill_rect_rgb(row, 0, w, 1, _DEFAULT_BG)

        # Badge: read from overlay host via context
        badge, badge_bg, badge_fg = get_badge()

        badge_width = 0
        if badge:
            badge_width = wcswidth(f"{badge} ")

        # Build left text: "repo  branch"
        left_text = f"{self._repo_name}  {self._branch_name}"
        left_width = wcswidth(left_text) + badge_width

        # Build right text: mode + tab name + key
        tab_suffix = f" [{self._current_tab_key}]" if self._current_tab_key else ""
        if self._mode:
            right_text = f"[{self._mode}]  {self._current_tab}{tab_suffix}"
        else:
            right_text = f"{self._current_tab}{tab_suffix}"
        right_width = wcswidth(right_text)

        # Build center: ahead/behind indicators
        center_parts = []
        if self._ahead > 0:
            center_parts.append(f"\u2191{self._ahead}")
        if self._behind > 0:
            center_parts.append(f"\u2193{self._behind}")
        center_text = " ".join(center_parts)
        center_width = wcswidth(center_text)

        # Layout: left | center | right
        total_needed = (
            left_width + (2 if center_text else 0) + center_width + right_width
        )
        available = w

        if total_needed > available and center_text:
            center_text = ""
            center_width = 0
            total_needed = left_width + right_width

        if total_needed > available:
            max_left = max(0, available - right_width - 1)
            left_text = truncate_by_width(left_text, max_left) + "\u2026"
            left_width = wcswidth(left_text)

        # Draw badge before repo name
        x = 0
        if badge:
            badge_str = f"{badge} "
            surface.draw_text_rgb(
                row,
                x,
                badge_str,
                fg=badge_fg or self._theme.fg_primary,
                bg=badge_bg or self._theme.bg_active,
                bold=True,
            )
            x += wcswidth(badge_str)

        # Draw left (repo + branch) with branch in accent cyan
        surface.draw_text_rgb(
            row, x, self._repo_name, fg=self._theme.fg_primary, bg=_DEFAULT_BG
        )
        x += wcswidth(self._repo_name)
        surface.draw_text_rgb(row, x, "  ", fg=self._theme.fg_dim, bg=_DEFAULT_BG)
        x += 2
        surface.draw_text_rgb(
            row,
            x,
            self._branch_name,
            fg=self._theme.accent_cyan,
            bg=_DEFAULT_BG,
        )

        # Draw center (ahead/behind)
        if center_text:
            center_x = max(0, (w - center_width) // 2)
            x = center_x
            if self._ahead > 0:
                ahead_text = f"\u2191{self._ahead}"
                surface.draw_text_rgb(
                    row, x, ahead_text, fg=self._theme.accent_green, bg=_DEFAULT_BG
                )
                x += wcswidth(ahead_text) + 1
            if self._behind > 0:
                behind_text = f"\u2193{self._behind}"
                surface.draw_text_rgb(
                    row, x, behind_text, fg=self._theme.accent_yellow, bg=_DEFAULT_BG
                )

        # Draw right: mode bright+bold, tab name muted, key suffix primary
        right_x = max(0, w - right_width)
        if self._mode:
            mode_text = f"[{self._mode}]"
            mode_w = wcswidth(mode_text)
            surface.draw_text_rgb(
                row,
                right_x,
                mode_text,
                fg=self._theme.fg_primary,
                bg=_DEFAULT_BG,
                bold=True,
            )
            rest = f"  {self._current_tab}"
            rest_w = wcswidth(rest)
            surface.draw_text_rgb(
                row,
                right_x + mode_w,
                rest,
                fg=self._theme.fg_muted,
                bg=_DEFAULT_BG,
                bold=True,
            )
            if self._current_tab_key:
                key_text = f" [{self._current_tab_key}]"
                surface.draw_text_rgb(
                    row,
                    right_x + mode_w + rest_w,
                    key_text,
                    fg=self._theme.fg_primary,
                    bg=_DEFAULT_BG,
                    bold=True,
                )
        else:
            tab_text = self._current_tab
            tab_w = wcswidth(tab_text)
            surface.draw_text_rgb(
                row,
                right_x,
                tab_text,
                fg=self._theme.fg_muted,
                bg=_DEFAULT_BG,
                bold=True,
            )
            if self._current_tab_key:
                key_text = f" [{self._current_tab_key}]"
                surface.draw_text_rgb(
                    row,
                    right_x + tab_w,
                    key_text,
                    fg=self._theme.fg_primary,
                    bg=_DEFAULT_BG,
                    bold=True,
                )


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
