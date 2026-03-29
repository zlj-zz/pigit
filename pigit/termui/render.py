# -*- coding: utf-8 -*-
"""
Module: pigit/termui/render.py
Description: Session-bound Renderer for ANSI drawing (1-based row/column).
Author: Project Team
Date: 2026-03-26
"""

from __future__ import annotations

from typing import TYPE_CHECKING, List, Sequence, Tuple

if TYPE_CHECKING:
    from pigit.termui.session import Session


class Renderer:
    """
    All terminal painting for the Git TUI goes through this type.

    Instances are always tied to a live :class:`~pigit.termui.session.Session`
    (``Session.renderer``).
    """

    def __init__(self, session: "Session") -> None:
        self._out = session.stdout

    def write(self, text: str) -> None:
        self._out.write(text)

    def flush(self) -> None:
        self._out.flush()

    def clear_screen(self) -> None:
        # Full clear then CUP (1,1), aligned with historical full-screen Git TUI.
        self._out.write("\033[2J\033[0;0f")
        self.move_cursor(1, 1)
        self.flush()

    def move_cursor(self, row: int, col: int) -> None:
        """Move cursor to 1-based ``row`` and ``col`` (inclusive), ECMA-48 CUP."""

        self._out.write(f"\033[{row};{col}f")

    def erase_line_to_end(self) -> None:
        """Erase from cursor to end of line (EL0); used by full-screen list picker."""

        self._out.write("\033[K")

    def draw_absolute_row(self, row: int, text: str) -> None:
        """
        Paint one logical line at a fixed 1-based terminal row.

        Current caller: :class:`~pigit.termui.component_list_picker.SearchableListPicker`
        (status/footer pinning). May generalize to other full-screen UIs later.
        """

        self.move_cursor(row, 1)
        self.erase_line_to_end()
        self._out.write(text)

    def hide_cursor(self) -> None:
        self._out.write("\033[?25l")

    def show_cursor(self) -> None:
        self._out.write("\033[?25h")

    def draw_block(
        self, lines: Sequence[str], row: int, col: int, width: int, height: int
    ) -> None:
        """
        Fill a rectangular area with lines, clipping to ``width`` / ``height``.

        Use this for a fixed viewport: each line is truncated or padded to
        ``width`` within ``height`` rows. Prefer :meth:`draw_panel` for block
        regions that mirror the historical full-screen component contract (erase
        full width per row, then paint content and blank trailing rows up to a
        last row index).
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
        Draw a multi-line block in the style of the historical Git TUI ``Render.draw``.

        For each content row: move to ``(x + row_index, y)``, erase the full
        logical width with spaces, then write the line. Rows from below the
        content through ``size[1]`` (last row index) are blanked the same way.
        ``size`` is ``(column_width, last_row_1_based)`` as in the legacy API.

        Do not substitute :meth:`draw_block` here: ``draw_block`` clips to a
        height/width window with ``ljust`` truncation; ``draw_panel`` erases
        the full width per row and uses the second component of ``size`` as an
        inclusive end row for blanking.
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
