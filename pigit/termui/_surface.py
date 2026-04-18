# -*- coding: utf-8 -*-
"""
Module: pigit/termui/_surface.py
Description: 2-D character buffer for declarative terminal drawing.
Author: Zev
Date: 2026-04-19
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal, Optional

from pigit.termui.wcwidth_table import (
    _char_width,
    pad_by_width,
    truncate_by_width,
    wcswidth,
)

# ANSI SGR sequences (e.g. ``\033[31m``, ``\033[0m``).
_ANSI_SGR_RE = re.compile(r"\x1b\[(?:\d{1,3}(?:;\d{1,3})*)?m")

# Box-drawing (UTF-8).
_BOX_H = "\u2500"
_BOX_V = "\u2502"
_BOX_TL = "\u250c"
_BOX_TR = "\u2510"
_BOX_BL = "\u2514"
_BOX_BR = "\u2518"


@dataclass(frozen=True)
class Cell:
    """One terminal cell.

    ``style`` stores the raw ANSI SGR prefix (e.g. ``\033[31m``) so that
    components which already emit coloured text can keep doing so during
    the Surface migration.  ``Renderer.render_surface`` wraps each cell
    independently with ``style + char + \033[0m``; callers should only put
    the opening SGR sequence in ``style`` and never include a reset.
    """

    char: str = " "
    style: str = ""


_BLANK_CELL = Cell()


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

    def draw_row(self, row: int, text: str, align: Literal["left", "center"] = "left") -> None:
        if row < 0 or row >= self.height:
            return
        self._parent.draw_row(self._row + row, text, align)

    def draw_box(
        self, row: int, col: int, width: int, height: int, title=None
    ) -> None:
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
        return _Subsurface(self._parent, self._row + row, self._col + col, width, height)


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
        self._rows: list[list[Cell]] = [
            [Cell() for _ in range(width)] for _ in range(height)
        ]

    def clear(self) -> None:
        """Reset every cell to a blank space."""
        for row in self._rows:
            for i in range(self.width):
                row[i] = _BLANK_CELL

    def draw_text(self, row: int, col: int, text: str) -> None:
        """Write text starting at (row, col), clipping to bounds.

        Inline ANSI SGR sequences are parsed and applied to subsequent cells
        as ``Cell.style`` so that upstream components can pass pre-coloured
        strings without breaking grid layout.
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
                    self._rows[row][cur_col] = Cell(ch, style=current_style)
                    if w == 2:
                        self._rows[row][cur_col + 1] = Cell("")
                cur_col += w
            seq = m.group(0)
            current_style = "" if seq == "\x1b[0m" else seq
            pos = m.end()
        for ch in text[pos:]:
            if cur_col >= self.width:
                return
            w = _char_width(ord(ch))
            if cur_col >= 0 and cur_col + w <= self.width:
                self._rows[row][cur_col] = Cell(ch, style=current_style)
                if w == 2:
                    self._rows[row][cur_col + 1] = Cell("")
            cur_col += w

    def draw_row(self, row: int, text: str, align: Literal["left", "center"] = "left") -> None:
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
            pad = max(0, (width - wcswidth(title_text)) // 2)
            self.draw_text(row, col + 1 + pad, title_text)

    def fill_rect(
        self, row: int, col: int, width: int, height: int, char: str = " "
    ) -> None:
        """Fill a rectangular area starting at (row, col)."""
        ch = char[0] if char else " "
        cell = Cell(ch)
        for r in range(row, min(row + height, self.height)):
            for c in range(col, min(col + width, self.width)):
                if 0 <= r < self.height and 0 <= c < self.width:
                    self._rows[r][c] = cell

    def subsurface(self, row: int, col: int, width: int, height: int) -> "_Subsurface":
        """Return a proxy that translates local coordinates to this surface."""
        return _Subsurface(self, row, col, width, height)

    def rows(self) -> list[list[Cell]]:
        """Return the internal row buffers for Renderer output.

        This exposes the 2-D cell grid directly; callers should treat
        each row as read-only and not mutate cells in place.
        """
        return self._rows

    def lines(self) -> list[str]:
        """Flatten buffer to strings for Renderer output."""
        return ["".join(cell.char for cell in row) for row in self._rows]
