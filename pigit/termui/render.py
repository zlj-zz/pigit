# -*- coding: utf-8 -*-
"""
Module: pigit/termui/render.py
Description: Session- or stdout-bound Renderer for ANSI drawing (1-based row/column).
Author: Project Team
Date: 2026-03-26
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, List, Optional, Sequence, TextIO, Tuple, Union

if TYPE_CHECKING:
    from pigit.termui.session import Session


class _StdoutWrapper:
    """Bind :class:`Renderer` to a :class:`~io.TextIO` stream without a live :class:`Session`."""

    __slots__ = ("stdout",)

    def __init__(self, stdout: TextIO) -> None:
        self.stdout = stdout


class Renderer:
    """
    All terminal painting for the Git TUI goes through this type.

    ``draw_panel`` matches the legacy ``tui.console.Render.draw`` contract used by list views.
    """

    def __init__(self, sink: Union["Session", _StdoutWrapper]) -> None:
        self._out = sink.stdout

    def write(self, text: str) -> None:
        self._out.write(text)

    def flush(self) -> None:
        self._out.flush()

    def clear_screen(self) -> None:
        # Same sequence as legacy Render.clear_screen: full clear then CUP (1,1).
        self._out.write("\033[2J\033[0;0f")
        self.move_cursor(1, 1)
        self.flush()

    def move_cursor(self, row: int, col: int) -> None:
        """Move cursor to 1-based ``row`` and ``col`` (inclusive), ECMA-48 CUP."""

        self._out.write(f"\033[{row};{col}f")

    def hide_cursor(self) -> None:
        self._out.write("\033[?25l")

    def show_cursor(self) -> None:
        self._out.write("\033[?25h")

    def draw_block(
        self, lines: Sequence[str], row: int, col: int, width: int, height: int
    ) -> None:
        """
        Fill a rectangular area with lines, clipping to ``width``/``height``.

        Prefer :meth:`draw_panel` for component tree drawing (matches old ``Render.draw``).
        """

        cur = row
        for i in range(height):
            line = lines[i] if i < len(lines) else ""
            self.move_cursor(cur, col)
            self._out.write(line[:width].ljust(min(len(line), width)))
            cur += 1
        self.flush()

    def draw_panel(self, content: List[str], x: int, y: int, size: Tuple[int, int]) -> None:
        """
        Block draw compatible with legacy ``Render.draw`` (row ``x``, column ``y``, ``size`` = width + last row).

        For each row: move cursor, erase full width with spaces, write the line; then blank any remaining rows.
        """

        col_width, row_end = size
        cur_row = x
        for line in content:
            self.move_cursor(cur_row, y)
            self._out.write(" " * col_width)
            self.move_cursor(cur_row, y)
            self._out.write(line)
            cur_row += 1
        while cur_row <= row_end:
            self.move_cursor(cur_row, y)
            self._out.write(" " * col_width)
            cur_row += 1
        self.flush()


def renderer_for_stdout(stdout: Optional[TextIO] = None) -> Renderer:
    """Renderer for the non-session path (legacy ``PosixInput`` / tests)."""

    return Renderer(_StdoutWrapper(stdout if stdout is not None else sys.stdout))
