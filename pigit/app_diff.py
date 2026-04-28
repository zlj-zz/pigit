# -*- coding: utf-8 -*-
"""
Module: pigit/app_diff.py
Description: DiffViewer with TrueColor diff rendering and heatmap column.
Author: Zev
Date: 2026-04-23
"""

from __future__ import annotations

import bisect
import logging
import re

from typing import Optional

from pigit.termui import (
    ActionEventType,
    Component,
    LineTextBrowser,
    SyntaxTokenizer,
    keys,
    palette,
    bind_keys,
    plain,
)
from pigit.termui.wcwidth_table import truncate_by_width, wcswidth

from .app_theme import THEME

_logger = logging.getLogger(__name__)

_HUNK_HEADER_RE = re.compile(r"@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@")


class DiffViewer(LineTextBrowser):
    """Diff viewer with TrueColor background rendering, line numbers, and heatmap column."""

    _CACHE_MAX = 64
    LINE_NO_WIDTH = 5
    LINE_NO_STR_WIDTH = 4  # LINE_NO_WIDTH - 1
    SCROLL_PAGE_SIZE = 5
    TAB_WIDTH = 8
    DENSITY_SHORT = 10
    DENSITY_MEDIUM = 30
    DENSITY_LONG = 60
    BORDER_ROWS = 2
    BORDER_COLS = 2

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
        self._tokenizer = SyntaxTokenizer()
        self._lang = "generic"
        self._multiline_mask: list[Optional[str]] = []
        # _render_tokens holds (text, fg_color, display_width) per token
        self._render_tokens: list[list[tuple[str, tuple[int, int, int], int]]] = []
        self._hunk_indices: list[int] = []

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
        self._content = []
        for line in diff_lines:
            cleaned = plain(line).replace("\r", "")
            if "\t" in cleaned:
                cleaned = cleaned.expandtabs(self.TAB_WIDTH)
            self._content.append(cleaned)
        self._compute_heatmap()
        self._compute_line_numbers()
        if self.i_cache_key:
            self._lang = self._tokenizer.detect_language(self.i_cache_key)
        self._multiline_mask = self._tokenizer.compute_multiline_mask(
            self._content, self._lang
        )
        self._render_tokens = self._pre_tokenize()
        self._hunk_indices = [
            i for i, line in enumerate(self._content) if line.startswith("@@")
        ]

    def _pre_tokenize(self) -> list[list[tuple[str, tuple[int, int, int], int]]]:
        """Pre-tokenize all lines, resolve colors, and compute display widths."""
        result: list[list[tuple[str, tuple[int, int, int], int]]] = []
        for i, line in enumerate(self._content):
            if line.startswith("@@"):
                tokens = self._tokenizer.tokenize_diff_hunk(line)
            elif line.startswith("\\"):
                result.append([])
                continue
            else:
                code = line[1:] if line and line[0] in "+- " else line
                ml_type = (
                    self._multiline_mask[i] if i < len(self._multiline_mask) else None
                )
                if ml_type is not None:
                    tokens = [(code, ml_type)]
                elif self._lang == "md":
                    tokens = self._tokenizer.tokenize_markdown(code)
                else:
                    tokens = self._tokenizer.tokenize(code, self._lang)
            result.append(
                [
                    (
                        text,
                        self._tokenizer.resolve_color(ttype, self._lang),
                        wcswidth(text),
                    )
                    for text, ttype in tokens
                ]
            )
        return result

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
            elif isinstance(content, str):
                self.set_content(content.splitlines())
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
        self.scroll_down(self.SCROLL_PAGE_SIZE)

    @bind_keys("K")
    def _scroll_page_up(self) -> None:
        self.scroll_up(self.SCROLL_PAGE_SIZE)

    @bind_keys("]")
    def _next_hunk(self) -> None:
        """Jump to next hunk header (@@ line)."""
        if not self._hunk_indices:
            return
        pos = bisect.bisect_right(self._hunk_indices, self._i)
        if pos < len(self._hunk_indices):
            self._i = self._hunk_indices[pos]

    @bind_keys("[")
    def _prev_hunk(self) -> None:
        """Jump to previous hunk header (@@ line)."""
        if not self._hunk_indices:
            return
        pos = bisect.bisect_left(self._hunk_indices, self._i) - 1
        if pos >= 0:
            self._i = self._hunk_indices[pos]

    def _compute_heatmap(self) -> None:
        """Compute density symbol and color for each line."""
        self._heatmap = []
        self._heatmap_colors = []
        for line in self._content:
            sym, color = self._heatmap_entry(line)
            self._heatmap.append(sym)
            self._heatmap_colors.append(color)

    def _heatmap_entry(self, line: str) -> tuple[str, tuple[int, int, int]]:
        """Return (density_symbol, color) for a single diff line."""
        if line.startswith("+"):
            density = self._line_density(line)
            return (
                ["░", "▒", "▓", "█"][min(density, 3)],
                THEME.accent_green,
            )
        if line.startswith("-"):
            density = self._line_density(line)
            return (
                ["░", "▒", "▓", "█"][min(density, 3)],
                THEME.accent_red,
            )
        return " ", THEME.fg_dim

    def _line_density(self, line: str) -> int:
        """Heuristic density based on line length."""
        length = len(line.strip())
        if length < self.DENSITY_SHORT:
            return 0
        if length < self.DENSITY_MEDIUM:
            return 1
        if length < self.DENSITY_LONG:
            return 2
        return 3

    def _compute_line_numbers(self) -> None:
        """Compute line numbers for each diff line by parsing @@ headers."""
        self._line_numbers = []
        old_line = 0
        new_line = 0
        for line in self._content:
            if line.startswith("@@"):
                m = _HUNK_HEADER_RE.search(line)
                if m:
                    old_line = int(m.group(1))
                    new_line = int(m.group(2))
                else:
                    _logger.warning("Unexpected @@ line format: %r", line)
                    old_line = 0
                    new_line = 0
                self._line_numbers.append("")
            elif line.startswith("+"):
                self._line_numbers.append(str(new_line).rjust(self.LINE_NO_STR_WIDTH))
                new_line += 1
            elif line.startswith("-"):
                self._line_numbers.append(str(old_line).rjust(self.LINE_NO_WIDTH - 1))
                old_line += 1
            elif line.startswith("\\"):
                self._line_numbers.append("")
            else:
                # Context line
                self._line_numbers.append(str(new_line).rjust(self.LINE_NO_STR_WIDTH))
                old_line += 1
                new_line += 1

    def resize(self, size: tuple[int, int]) -> None:
        # Reserve BORDER_ROWS for top/bottom borders
        self._max_line = max(0, size[1] - self.BORDER_ROWS)
        # Bypass LineTextBrowser.resize() which would reset _max_line to full height
        super(LineTextBrowser, self).resize(size)

    def _draw_diff_line(
        self,
        surface,
        row: int,
        line: str,
        idx: int,
        *,
        x_offset: int,
        main_w: int,
        heatmap_x: int,
        fill_width: int,
    ) -> None:
        """Render one diff line: background, line number, text, and heatmap."""
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

        if bg != palette.DEFAULT_BG:
            surface.fill_rect_rgb(row, x_offset, fill_width, 1, bg)

        line_no = self._line_numbers[idx] if idx < len(self._line_numbers) else ""
        if line_no:
            surface.draw_text_rgb(row, x_offset, line_no, fg=THEME.fg_dim, bg=bg)

        # ── Syntax-highlighted text rendering ──
        text_start_col = x_offset + self.LINE_NO_WIDTH
        col = text_start_col
        max_col = text_start_col + main_w
        tokens: list[tuple[str, tuple[int, int, int], int]] = []

        if line.startswith("@@"):
            tokens = self._render_tokens[idx]
        elif line.startswith("\\"):
            # "\ No newline at end of file" — draw as comment
            surface.draw_text_rgb(row, text_start_col, line, fg=THEME.fg_dim, bg=bg)
        else:
            if line and line[0] in "+-":
                prefix = line[0]
                prefix_fg = THEME.accent_green if prefix == "+" else THEME.accent_red
                surface.draw_text_rgb(row, col, prefix, fg=prefix_fg, bg=bg)
                col += 1

            tokens = self._render_tokens[idx]

        self._draw_tokens(surface, row, col, max_col, tokens, bg)

        sym = self._heatmap[idx]
        color = self._heatmap_colors[idx]
        surface.draw_text_rgb(row, heatmap_x, sym, fg=color, bg=bg)

    def _draw_tokens(
        self,
        surface,
        row: int,
        col: int,
        max_col: int,
        tokens: list[tuple[str, tuple[int, int, int], int]],
        bg: tuple[int, int, int],
    ) -> None:
        """Draw syntax tokens with width-aware truncation."""
        for token_text, token_fg, token_width in tokens:
            if col + token_width > max_col:
                avail = max_col - col
                if avail > 1:
                    token_text = truncate_by_width(token_text, avail - 1) + "…"
                    surface.draw_text_rgb(row, col, token_text, fg=token_fg, bg=bg)
                break
            surface.draw_text_rgb(row, col, token_text, fg=token_fg, bg=bg)
            col += token_width

    def _render_surface(self, surface) -> None:
        if not self._content:
            return
        w = surface.width
        h = surface.height
        if w <= self.LINE_NO_WIDTH + 3 or h < self.BORDER_ROWS + 1:
            self._render_surface_borderless(surface)
            return

        surface.draw_box_rgb(0, 0, w, h, fg=THEME.fg_dim, bg=palette.DEFAULT_BG)

        content_h = h - self.BORDER_ROWS
        content_w = w - self.BORDER_COLS
        main_w = content_w - self.LINE_NO_WIDTH - 1
        end = min(self._i + content_h, len(self._content))

        for idx in range(self._i, end):
            row = idx - self._i + 1
            self._draw_diff_line(
                surface,
                row,
                self._content[idx],
                idx,
                x_offset=1,
                main_w=main_w,
                heatmap_x=w - self.BORDER_COLS,
                fill_width=w - self.BORDER_COLS,
            )

        last_content_row = end - self._i
        blank_count = h - 1 - (last_content_row + 1)
        if blank_count > 0:
            surface.fill_rect_rgb(
                last_content_row + 1,
                1,
                w - self.BORDER_COLS,
                blank_count,
                palette.DEFAULT_BG,
            )

    def _render_surface_borderless(self, surface) -> None:
        """Original rendering without box border, used when surface is too small."""
        w = surface.width
        h = surface.height
        if w <= self.LINE_NO_WIDTH + 1:
            return

        main_w = w - self.LINE_NO_WIDTH - 1
        end = min(self._i + h, len(self._content))

        for idx in range(self._i, end):
            row = idx - self._i
            self._draw_diff_line(
                surface,
                row,
                self._content[idx],
                idx,
                x_offset=0,
                main_w=main_w,
                heatmap_x=w - 1,
                fill_width=w,
            )
