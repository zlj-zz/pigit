# -*- coding: utf-8 -*-
"""
Module: pigit/termui/_surface.py
Description: 2-D character buffer for declarative terminal drawing.
Author: Zev
Date: 2026-04-19
"""

from __future__ import annotations

import re
from typing import Literal, Optional

from .wcwidth_table import (
    _char_width,
    pad_by_width,
    truncate_by_width,
    wcswidth,
)

_DEFAULT_FG: tuple[int, int, int] = (220, 220, 230)
_DEFAULT_BG: tuple[int, int, int] = (18, 18, 22)

# ANSI SGR sequences (e.g. ``\033[31m``, ``\033[0m``).
_ANSI_SGR_RE = re.compile(r"\x1b\[(?:\d{1,3}(?:;\d{1,3})*)?m")

# Box-drawing (UTF-8).
_BOX_H = "\u2500"
_BOX_V = "\u2502"
_BOX_TL = "\u250c"
_BOX_TR = "\u2510"
_BOX_BL = "\u2514"
_BOX_BR = "\u2518"


class FlatCell:
    """TrueColor-aware terminal cell with structured style attributes.

    ``fg`` and ``bg`` are RGB tuples. ``bold`` controls weight.
    When ``ansi_style`` is set, it takes precedence (legacy mode).

    The ``style`` parameter is a backward-compatibility alias for
    ``ansi_style`` so existing ``Cell(char, style="...")`` calls
    continue to work.
    """

    __slots__ = ("char", "fg", "bg", "bold", "ansi_style", "_hash")

    def __init__(
        self,
        char: str = " ",
        style: str = "",
        fg: tuple[int, int, int] = _DEFAULT_FG,
        bg: tuple[int, int, int] = _DEFAULT_BG,
        bold: bool = False,
        ansi_style: Optional[str] = None,
    ) -> None:
        self.char = char
        self.fg = fg
        self.bg = bg
        self.bold = bold
        # Backward compat: 'style' kwarg maps to ansi_style
        self.ansi_style = ansi_style if ansi_style is not None else (style or None)
        self._hash = hash((self.char, self.fg, self.bg, self.bold, self.ansi_style))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, FlatCell):
            return NotImplemented
        return (
            self.char == other.char
            and self.fg == other.fg
            and self.bg == other.bg
            and self.bold == other.bold
            and self.ansi_style == other.ansi_style
        )

    def __hash__(self) -> int:
        return self._hash

    @property
    def style(self) -> str:
        """Backward compatibility alias for ``ansi_style``."""
        return self.ansi_style or ""

    def __repr__(self) -> str:
        return (
            f"FlatCell(char={self.char!r}, fg={self.fg}, bg={self.bg}, "
            f"bold={self.bold}, ansi_style={self.ansi_style!r})"
        )


# Backward compatibility: Cell is an alias for FlatCell.
Cell = FlatCell

_BLANK_CELL = FlatCell()


class _Subsurface:
    """Proxy that translates local coordinates to a parent Surface."""

    def __init__(
        self, parent: "Surface", row: int, col: int, width: int, height: int
    ) -> None:
        self._parent = parent
        self._row = row
        self._col = col
        self.width = max(0, width)
        self.height = max(0, height)

    def __repr__(self) -> str:
        return f"_Subsurface({self.width}x{self.height} @ {self._row},{self._col})"

    def _to_parent(self, row: int, col: int) -> tuple[int, int]:
        return self._row + row, self._col + col

    def _clip(
        self, row: int, col: int, width: int, height: int
    ) -> tuple[int, int, int, int] | None:
        r, c = self._to_parent(row, col)
        w = min(width, self.width - col)
        h = min(height, self.height - row)
        if w <= 0 or h <= 0:
            return None
        return r, c, w, h

    def draw_text(self, row: int, col: int, text: str) -> None:
        if row < 0 or row >= self.height or col >= self.width:
            return
        r, c = self._to_parent(row, col)
        self._parent.draw_text(r, c, text)

    def draw_row(
        self, row: int, text: str, align: Literal["left", "center"] = "left"
    ) -> None:
        if row < 0 or row >= self.height:
            return
        self._parent.draw_row(self._row + row, text, align)

    def draw_box(self, row: int, col: int, width: int, height: int, title=None) -> None:
        clipped = self._clip(row, col, width, height)
        if clipped is None:
            return
        self._parent.draw_box(*clipped, title)

    def fill_rect(
        self, row: int, col: int, width: int, height: int, char: str = " "
    ) -> None:
        clipped = self._clip(row, col, width, height)
        if clipped is None:
            return
        self._parent.fill_rect(*clipped, char)

    def subsurface(self, row: int, col: int, width: int, height: int) -> "_Subsurface":
        return _Subsurface(
            self._parent, self._row + row, self._col + col, width, height
        )

    # --- RGB proxy methods ---

    def draw_text_rgb(
        self,
        row: int,
        col: int,
        text: str,
        fg: tuple[int, int, int],
        bg: tuple[int, int, int] = _DEFAULT_BG,
        bold: bool = False,
    ) -> None:
        if row < 0 or row >= self.height or col >= self.width:
            return
        r, c = self._to_parent(row, col)
        self._parent.draw_text_rgb(r, c, text, fg=fg, bg=bg, bold=bold)

    def fill_rect_rgb(
        self, row: int, col: int, width: int, height: int, bg: tuple[int, int, int]
    ) -> None:
        clipped = self._clip(row, col, width, height)
        if clipped is None:
            return
        self._parent.fill_rect_rgb(*clipped, bg)

    def draw_row_rgb(
        self,
        row: int,
        text: str,
        fg: tuple[int, int, int],
        bg: tuple[int, int, int] = _DEFAULT_BG,
        bold: bool = False,
        align: Literal["left", "center"] = "left",
    ) -> None:
        if row < 0 or row >= self.height:
            return
        self._parent.draw_row_rgb(
            self._row + row, text, fg=fg, bg=bg, bold=bold, align=align
        )


class Surface:
    """2-D character buffer for declarative terminal drawing.

    Coordinates follow terminal convention: ``row`` is the vertical axis
    (0-based, top to bottom) and ``col`` is the horizontal axis
    (0-based, left to right). For APIs that accept a single ``x`` argument,
    ``x`` means ``row`` to stay consistent with ``Component.x``.
    """

    def __init__(self, width: int, height: int) -> None:
        self.width = width
        self.height = height
        self._rows: list[list[FlatCell]] = [
            [FlatCell() for _ in range(width)] for _ in range(height)
        ]

    def __repr__(self) -> str:
        return f"Surface({self.width}x{self.height})"

    def clear(self) -> None:
        """Reset every cell to a blank space."""
        for row in self._rows:
            for i in range(self.width):
                row[i] = _BLANK_CELL

    def draw_text(self, row: int, col: int, text: str) -> None:
        """Write text starting at (row, col), clipping to bounds.

        Inline ANSI SGR sequences are parsed and applied to subsequent cells
        as ``FlatCell.ansi_style`` so that upstream components can pass
        pre-coloured strings without breaking grid layout.
        """
        if row < 0 or row >= self.height:
            return
        cur_col = col
        current_style = ""
        pos = 0
        for m in _ANSI_SGR_RE.finditer(text):
            for ch in text[pos : m.start()]:
                if cur_col >= self.width:
                    return
                w = _char_width(ord(ch))
                if cur_col >= 0 and cur_col + w <= self.width:
                    self._rows[row][cur_col] = FlatCell(ch, style=current_style)
                    if w == 2:
                        self._rows[row][cur_col + 1] = FlatCell("")
                cur_col += w
            seq = m.group(0)
            current_style = "" if seq == "\x1b[0m" else seq
            pos = m.end()
        for ch in text[pos:]:
            if cur_col >= self.width:
                return
            w = _char_width(ord(ch))
            if cur_col >= 0 and cur_col + w <= self.width:
                self._rows[row][cur_col] = FlatCell(ch, style=current_style)
                if w == 2:
                    self._rows[row][cur_col + 1] = FlatCell("")
            cur_col += w

    def draw_row(
        self, row: int, text: str, align: Literal["left", "center"] = "left"
    ) -> None:
        """Write a full-width row, truncated or padded with spaces."""
        if row < 0 or row >= self.height or self.width <= 0:
            return
        text_width = wcswidth(text)
        if text_width > self.width:
            text = truncate_by_width(text, self.width - 1) + "\u2026"
            text_width = wcswidth(text)
        if align == "center":
            pad_left = max(0, (self.width - text_width) // 2)
            text = " " * pad_left + text
        padded = pad_by_width(text, self.width)
        self.draw_text(row, 0, padded)

    def draw_box(
        self,
        row: int,
        col: int,
        width: int,
        height: int,
        title: Optional[str] = None,
    ) -> None:
        """Draw a box-drawing border starting at (row, col)."""
        if width < 2 or height < 2:
            return

        top = _BOX_TL + _BOX_H * (width - 2) + _BOX_TR
        self.draw_text(row, col, top)
        for r in range(row + 1, row + height - 1):
            self.draw_text(r, col, _BOX_V)
            self.draw_text(r, col + width - 1, _BOX_V)
        bottom = _BOX_BL + _BOX_H * (width - 2) + _BOX_BR
        self.draw_text(row + height - 1, col, bottom)

        if title:
            title_text = f" {title[: max(0, width - 4)]} "
            title_text = truncate_by_width(title_text, max(0, width - 2))
            pad = max(0, (width - 2 - wcswidth(title_text)) // 2)
            self.draw_text(row, col + 1 + pad, title_text)

    def fill_rect(
        self, row: int, col: int, width: int, height: int, char: str = " "
    ) -> None:
        """Fill a rectangular area starting at (row, col)."""
        ch = char[0] if char else " "
        cell = FlatCell(ch)
        for r in range(row, min(row + height, self.height)):
            for c in range(col, min(col + width, self.width)):
                if 0 <= r < self.height and 0 <= c < self.width:
                    self._rows[r][c] = cell

    def subsurface(self, row: int, col: int, width: int, height: int) -> "_Subsurface":
        """Return a proxy that translates local coordinates to this surface."""
        return _Subsurface(self, row, col, width, height)

    def subsurface_with_margin(
        self,
        row: int,
        col: int,
        width: int,
        height: int,
        margin_top: int = 0,
        margin_bottom: int = 0,
        margin_left: int = 0,
        margin_right: int = 0,
    ) -> "_Subsurface":
        """Return a subsurface inset by margins.

        Args:
            row, col, width, height: Base geometry.
            margin_top, margin_bottom, margin_left, margin_right:
                Pixels to inset from each edge.
        """
        return _Subsurface(
            self,
            row + margin_top,
            col + margin_left,
            max(0, width - margin_left - margin_right),
            max(0, height - margin_top - margin_bottom),
        )

    # ------------------------------------------------------------------ #
    # RGB drawing methods (TrueColor)
    # ------------------------------------------------------------------ #

    def draw_text_rgb(
        self,
        row: int,
        col: int,
        text: str,
        fg: tuple[int, int, int],
        bg: tuple[int, int, int] = _DEFAULT_BG,
        bold: bool = False,
    ) -> None:
        """Write text with explicit RGB foreground and background colors.

        Args:
            row, col: Starting position.
            text: String to write.
            fg: Foreground RGB tuple.
            bg: Background RGB tuple.
            bold: Whether to render in bold weight.
        """
        if row < 0 or row >= self.height:
            return
        cur_col = col
        for ch in text:
            if cur_col >= self.width:
                return
            w = _char_width(ord(ch))
            if cur_col >= 0 and cur_col + w <= self.width:
                self._rows[row][cur_col] = FlatCell(ch, fg=fg, bg=bg, bold=bold)
                if w == 2:
                    self._rows[row][cur_col + 1] = FlatCell("")
            cur_col += w

    def fill_rect_rgb(
        self, row: int, col: int, width: int, height: int, bg: tuple[int, int, int]
    ) -> None:
        """Fill a rectangular area with a solid background color.

        Existing character content is replaced with spaces.
        """
        cell = FlatCell(" ", bg=bg)
        for r in range(row, min(row + height, self.height)):
            for c in range(col, min(col + width, self.width)):
                if 0 <= r < self.height and 0 <= c < self.width:
                    self._rows[r][c] = cell

    def draw_row_rgb(
        self,
        row: int,
        text: str,
        fg: tuple[int, int, int],
        bg: tuple[int, int, int] = _DEFAULT_BG,
        bold: bool = False,
        align: Literal["left", "center"] = "left",
    ) -> None:
        """Write a full-width row with RGB colors.

        Text is truncated or padded with spaces to fill the row width.
        """
        if row < 0 or row >= self.height or self.width <= 0:
            return
        text_width = wcswidth(text)
        if text_width > self.width:
            text = truncate_by_width(text, self.width - 1) + "\u2026"
            text_width = wcswidth(text)
        if align == "center":
            pad_left = max(0, (self.width - text_width) // 2)
            text = " " * pad_left + text
        padded = pad_by_width(text, self.width)
        cur_col = 0
        for ch in padded:
            if cur_col >= self.width:
                break
            w = _char_width(ord(ch))
            if cur_col >= 0 and cur_col + w <= self.width:
                self._rows[row][cur_col] = FlatCell(ch, fg=fg, bg=bg, bold=bold)
                if w == 2:
                    self._rows[row][cur_col + 1] = FlatCell("")
            cur_col += w

    def fill_row_bg(self, row: int, bg: tuple[int, int, int]) -> None:
        """Fill the background of an entire row, preserving characters.

        Only the ``bg`` attribute is changed; ``fg``, ``bold``, and
        ``ansi_style`` are retained.
        """
        if row < 0 or row >= self.height:
            return
        for c in range(self.width):
            old = self._rows[row][c]
            self._rows[row][c] = FlatCell(
                old.char,
                fg=old.fg,
                bg=bg,
                bold=old.bold,
                ansi_style=old.ansi_style,
            )

    def rows(self) -> list[list[FlatCell]]:
        """Return the internal row buffers for Renderer output.

        This exposes the 2-D cell grid directly; callers should treat
        each row as read-only and not mutate cells in place.
        """
        return self._rows

    def lines(self) -> list[str]:
        """Flatten buffer to strings for Renderer output."""
        return ["".join(cell.char for cell in row) for row in self._rows]
