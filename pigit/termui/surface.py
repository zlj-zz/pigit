# -*- coding: utf-8 -*-
"""
Module: pigit/termui/surface.py
Description: 2-D character buffer for declarative terminal drawing.
Author: Zev
Date: 2026-04-16
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

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
                row[i] = Cell()

    def draw_text(self, row: int, col: int, text: str) -> None:
        """Write text starting at (row, col), clipping to bounds.

        Control characters (``\n``, ``\t``, ``\r``) are treated as ordinary
        printable characters and drawn inline. Callers must split multi-line
        text before calling this method.
        """
        if row < 0 or row >= self.height:
            return
        for i, ch in enumerate(text):
            c = col + i
            if 0 <= c < self.width:
                self._rows[row][c] = Cell(ch)

    def draw_row(self, row: int, text: str, align: str = "left") -> None:
        """Write a full-width row, truncated or padded with spaces.

        .. note::
           Current implementation uses ``len(text)`` as the display width.
           Wide characters (CJK) are not handled yet and should be addressed
           in a future phase (e.g. by integrating ``wcwidth``).
        """
        if row < 0 or row >= self.height or self.width <= 0:
            return
        if len(text) > self.width:
            text = text[: self.width - 1] + "…" if self.width > 1 else text[:self.width]
        if align == "center":
            pad_left = max(0, (self.width - len(text)) // 2)
            text = " " * pad_left + text
        padded = text.ljust(self.width)[: self.width]
        for i, ch in enumerate(padded):
            self._rows[row][i] = Cell(ch)

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
            title_text = title_text[: max(0, width - 2)]
            pad = max(0, (width - len(title_text)) // 2)
            self.draw_text(row, col + 1 + pad, title_text)

    def fill_rect(
        self, row: int, col: int, width: int, height: int, char: str = " "
    ) -> None:
        """Fill a rectangular area starting at (row, col)."""
        ch = char[0] if char else " "
        for r in range(row, min(row + height, self.height)):
            for c in range(col, min(col + width, self.width)):
                if 0 <= r < self.height and 0 <= c < self.width:
                    self._rows[r][c] = Cell(ch)

    def rows(self) -> list[list[Cell]]:
        """Return the internal row buffers for Renderer output.

        This exposes the 2-D cell grid directly; callers should treat
        each row as read-only and not mutate cells in place.
        """
        return self._rows

    def lines(self) -> list[str]:
        """Flatten buffer to strings for Renderer output."""
        return ["".join(cell.char for cell in row) for row in self._rows]
