# -*- coding: utf-8 -*-
"""
Module: pigit/app_diff.py
Description: DiffViewer with TrueColor diff rendering and heatmap column.
Author: Zev
Date: 2026-04-23
"""

from __future__ import annotations

import logging

from typing import Optional

from pigit.termui import (
    ActionEventType,
    Component,
    LineTextBrowser,
    keys,
    palette,
    bind_keys,
)
from pigit.termui.wcwidth_table import truncate_by_width, wcswidth

from .app_theme import THEME

_logger = logging.getLogger(__name__)


class DiffViewer(LineTextBrowser):
    """Diff viewer with TrueColor background rendering, line numbers, and heatmap column."""

    _CACHE_MAX = 64
    LINE_NO_WIDTH = 5

    def __init__(
        self,
        x: int = 1,
        y: int = 1,
        size: Optional[tuple[int, int]] = None,
    ) -> None:
        super().__init__(x, y, size, "")
        # LineTextBrowser sets _max_line to full height; adjust for border rows
        if self._size[1] >= 3:
            self._max_line = self._size[1] - 2
        self._heatmap: list[str] = []
        self._heatmap_colors: list[tuple[int, int, int]] = []
        self._line_numbers: list[str] = []
        self.come_from: Optional[Component] = None
        self.i_cache_key = ""
        self.i_cache: dict[str, int] = {}

    def set_content(self, diff_lines: list[str]) -> None:
        """Set diff content and pre-compute heatmap and line numbers.

        Tab characters are expanded to spaces (tabstop=8) because terminals
        render tabs as variable-width whitespace, while our width calculations
        treat every codepoint as width 1. Without expansion, tab-heavy diff
        lines overflow their allocated columns and corrupt borders.

        Carriage returns (``\\r``) are stripped because CRLF files cause
        ``\\r`` to reset the cursor to the start of the line, corrupting
        the rendered output.
        """
        self._content = [
            line.replace("\r", "").expandtabs(8) for line in diff_lines
        ]
        self._compute_heatmap()
        self._compute_line_numbers()

    def get_help_title(self) -> str:
        return "Diff"

    def get_help_entries(self) -> list[tuple[str, str]]:
        """Return help pairs for diff viewer."""
        return [
            ("j/k", "Navigate"),
            ("J/K", "Quick Navigate"),
            ("esc", "Back"),
        ]

    def update(self, action: ActionEventType, **data) -> None:
        if action is ActionEventType.goto:
            self.i_cache[self.i_cache_key] = self._i
            while len(self.i_cache) >= self._CACHE_MAX:
                del self.i_cache[next(iter(self.i_cache))]
            src = data.get("source")
            self.come_from = src if isinstance(src, Component) else None
            self.i_cache_key = data.get("key", "")
            content = data.get("content", "")
            if isinstance(content, list):
                self.set_content(content)
            else:
                self._content = content
                self._compute_heatmap()
                self._compute_line_numbers()
            self._i = self.i_cache.get(self.i_cache_key, 0)

    @bind_keys(keys.KEY_ESC)
    def _leave_display(self) -> None:
        if self.come_from is not None:
            self.emit(ActionEventType.goto, target=self.come_from)

    @bind_keys("j")
    def _scroll_line_down(self) -> None:
        self.scroll_down()

    @bind_keys("k")
    def _scroll_line_up(self) -> None:
        self.scroll_up()

    @bind_keys("J")
    def _scroll_page_down(self) -> None:
        self.scroll_down(5)

    @bind_keys("K")
    def _scroll_page_up(self) -> None:
        self.scroll_up(5)

    @bind_keys("]")
    def _next_hunk(self) -> None:
        """Jump to next hunk header (@@ line)."""
        if not self._content:
            return
        for idx in range(self._i + 1, len(self._content)):
            if self._content[idx].startswith("@@"):
                self._i = idx
                return

    @bind_keys("[")
    def _prev_hunk(self) -> None:
        """Jump to previous hunk header (@@ line)."""
        if not self._content:
            return
        for idx in range(self._i - 1, -1, -1):
            if self._content[idx].startswith("@@"):
                self._i = idx
                return

    def _compute_heatmap(self) -> None:
        """Compute density symbol and color for each line."""
        self._heatmap = []
        self._heatmap_colors = []
        for line in self._content:
            if line.startswith("+"):
                density = self._line_density(line)
                sym = ["░", "▒", "▓", "█"][min(density, 3)]
                color = THEME.accent_green
            elif line.startswith("-"):
                density = self._line_density(line)
                sym = ["░", "▒", "▓", "█"][min(density, 3)]
                color = THEME.accent_red
            elif line.startswith("@@"):
                sym = " "
                color = THEME.fg_dim
            else:
                sym = " "
                color = THEME.fg_dim
            self._heatmap.append(sym)
            self._heatmap_colors.append(color)

    def _line_density(self, line: str) -> int:
        """Heuristic density based on line length."""
        length = len(line.strip())
        if length < 10:
            return 0
        if length < 30:
            return 1
        if length < 60:
            return 2
        return 3

    def _compute_line_numbers(self) -> None:
        """Compute line numbers for each diff line by parsing @@ headers."""
        import re

        self._line_numbers = []
        old_line = 0
        new_line = 0
        for line in self._content:
            if line.startswith("@@"):
                m = re.search(r"@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@", line)
                if m:
                    old_line = int(m.group(1))
                    new_line = int(m.group(2))
                else:
                    _logger.warning("Unexpected @@ line format: %r", line)
                    old_line = 0
                    new_line = 0
                self._line_numbers.append("")
            elif line.startswith("+"):
                self._line_numbers.append(str(new_line))
                new_line += 1
            elif line.startswith("-"):
                self._line_numbers.append(str(old_line))
                old_line += 1
            elif line.startswith("\\"):
                self._line_numbers.append("")
            else:
                # Context line
                self._line_numbers.append(str(new_line))
                old_line += 1
                new_line += 1

    def resize(self, size: tuple[int, int]) -> None:
        # Reserve 2 rows for top/bottom borders
        self._max_line = max(0, size[1] - 2)
        # Bypass LineTextBrowser.resize() which would reset _max_line to full height
        super(LineTextBrowser, self).resize(size)

    def _render_surface(self, surface) -> None:
        if not self._content:
            return
        w = surface.width
        h = surface.height
        if w <= self.LINE_NO_WIDTH + 3 or h < 3:
            # Too small for box border, fall back to borderless rendering
            self._render_surface_borderless(surface)
            return

        # Draw outer box frame (content rows will overlay left/right borders with
        # their own background colors).
        surface.draw_box_rgb(0, 0, w, h, fg=THEME.fg_dim, bg=palette.DEFAULT_BG)

        # Content area is inset by 1 row and 1 column on each side
        content_h = h - 2
        content_w = w - 2
        main_w = content_w - self.LINE_NO_WIDTH - 1
        end = min(self._i + content_h, len(self._content))

        for idx in range(self._i, end):
            row = idx - self._i + 1  # +1 to skip top border
            if row >= h - 1:
                break
            line = self._content[idx]

            # Determine background color based on diff prefix
            if line.startswith("+"):
                bg = THEME.bg_success
                fg = THEME.fg_primary
            elif line.startswith("-"):
                bg = THEME.bg_danger
                fg = THEME.fg_primary
            elif line.startswith("@@"):
                bg = palette.DEFAULT_BG
                fg = THEME.accent_blue
            else:
                bg = palette.DEFAULT_BG
                fg = THEME.fg_primary

            # Fill only the content area background, keeping border columns
            # at the default background so the box frame remains clean.
            surface.fill_rect_rgb(row, 1, w - 2, 1, bg)

            # Draw line number (right-aligned in line-no column)
            line_no = self._line_numbers[idx] if idx < len(self._line_numbers) else ""
            if line_no:
                no_text = line_no.rjust(self.LINE_NO_WIDTH - 1)
                surface.draw_text_rgb(row, 1, no_text, fg=THEME.fg_dim, bg=bg)

            # Draw line text (truncate by display width, not character count)
            text = line
            if wcswidth(text) > main_w:
                text = truncate_by_width(text, main_w - 1) + "…"
            surface.draw_text_rgb(row, 1 + self.LINE_NO_WIDTH, text, fg=fg, bg=bg)

            # Draw heatmap
            sym = self._heatmap[idx]
            color = self._heatmap_colors[idx]
            surface.draw_text_rgb(row, w - 2, sym, fg=color, bg=bg)

        # When content is shorter than viewport, fill remaining rows with the
        # default background (outer box frame already drew left/right borders).
        last_content_row = end - self._i
        for blank_row in range(last_content_row + 1, h - 1):
            # Fill only the interior so the outer box frame borders remain.
            surface.fill_rect_rgb(blank_row, 1, w - 2, 1, palette.DEFAULT_BG)

    def _render_surface_borderless(self, surface) -> None:
        """Original rendering without box border, used when surface is too small."""
        w = surface.width
        h = surface.height
        if w <= self.LINE_NO_WIDTH + 1:
            return

        # Main area excludes line number column and rightmost heatmap column
        main_w = w - self.LINE_NO_WIDTH - 1
        # Use full height for borderless fallback (ignore _max_line border adjustment)
        end = min(self._i + h, len(self._content))

        for idx in range(self._i, end):
            row = idx - self._i
            if row >= h:
                break
            line = self._content[idx]

            # Determine background color based on diff prefix
            if line.startswith("+"):
                bg = THEME.bg_success
                fg = THEME.fg_primary
            elif line.startswith("-"):
                bg = THEME.bg_danger
                fg = THEME.fg_primary
            elif line.startswith("@@"):
                bg = palette.DEFAULT_BG
                fg = THEME.accent_blue
            else:
                bg = palette.DEFAULT_BG
                fg = THEME.fg_primary

            # Fill row background only for added/removed lines
            if bg != palette.DEFAULT_BG:
                surface.fill_rect_rgb(row, 0, w, 1, bg)

            # Draw line number (right-aligned in line-no column)
            line_no = self._line_numbers[idx] if idx < len(self._line_numbers) else ""
            if line_no:
                no_text = line_no.rjust(self.LINE_NO_WIDTH - 1)
                surface.draw_text_rgb(row, 0, no_text, fg=THEME.fg_dim, bg=bg)

            # Draw line text (truncate by display width, not character count)
            text = line
            if wcswidth(text) > main_w:
                text = truncate_by_width(text, main_w - 1) + "…"
            surface.draw_text_rgb(row, self.LINE_NO_WIDTH, text, fg=fg, bg=bg)

            # Draw heatmap in rightmost column
            sym = self._heatmap[idx]
            color = self._heatmap_colors[idx]
            surface.draw_text_rgb(row, w - 1, sym, fg=color, bg=bg)
