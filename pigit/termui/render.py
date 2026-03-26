# -*- coding: utf-8 -*-
"""
Module: pigit/termui/render.py
Description: Session-bound Renderer for ANSI drawing (1-based row/column like existing TUI).
Author: Project Team
Date: 2026-03-26
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Sequence

if TYPE_CHECKING:
    from pigit.termui.session import Session


class Renderer:
    """Write through a Session's stdout; avoids scattering raw ANSI outside this type."""

    def __init__(self, session: "Session") -> None:
        self._out = session.stdout

    def write(self, text: str) -> None:
        self._out.write(text)

    def flush(self) -> None:
        self._out.flush()

    def clear_screen(self) -> None:
        self._out.write("\033[2J\033[0;0f")
        self.flush()

    def move_cursor(self, row: int, col: int) -> None:
        """Move cursor to 1-based ``row`` and ``col`` (inclusive), ECMA-48 CUP."""

        self._out.write(f"\033[{row};{col}f")

    def hide_cursor(self) -> None:
        self._out.write("\033[?25l")

    def show_cursor(self) -> None:
        self._out.write("\033[?25h")

    def draw_block(self, lines: Sequence[str], row: int, col: int, width: int, height: int) -> None:
        """
        Fill a rectangular area with lines, clipping to ``width``/``height``.

        Coordinate system matches existing ``tui.console.Render.draw`` usage (row-major).
        """

        cur = row
        for i in range(height):
            line = lines[i] if i < len(lines) else ""
            self.move_cursor(cur, col)
            self._out.write(line[:width].ljust(min(len(line), width)))
            cur += 1
        self.flush()
