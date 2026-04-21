# -*- coding: utf-8 -*-
"""
Module: pigit/termui/_renderer.py
Description: Session-bound Renderer for ANSI drawing (1-based row/column).
Author: Zev
Date: 2026-04-19
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Sequence

if TYPE_CHECKING:
    from ._session import Session
    from ._surface import Cell, Surface


class Renderer:
    """
    All terminal painting for the Git TUI goes through this type.

    Instances are always tied to a live :class:`~pigit.termui.session.Session`
    (``Session.renderer``).
    """

    def __init__(self, session: "Session") -> None:
        self._out = session.stdout
        self._prev_frame: Optional[list[str]] = None
        self._prev_size: Optional[tuple[int, int]] = None
        self._cursor_pos: Optional[tuple[int, int]] = None
        self._last_cursor: Optional[tuple[int, int]] = None
        self._cursor_visible: bool = False

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

    def set_cursor(self, row: int, col: int) -> None:
        """Set cursor position in 0-based surface coordinates.

        ``render_surface`` will move the physical terminal cursor here
        and show it after the frame is drawn.  If never called, the
        cursor is hidden.
        """
        self._cursor_pos = (row, col)

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

    def draw_panel(
        self, content: list[str], x: int, y: int, size: tuple[int, int]
    ) -> None:
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

    def _row_to_str(self, row: list["Cell"]) -> str:
        parts = []
        last_style = ""
        for cell in row:
            if cell.char == "":
                continue
            if cell.style != last_style:
                if last_style:
                    parts.append("\033[0m")
                if cell.style:
                    parts.append(cell.style)
                last_style = cell.style
            parts.append(cell.char)
        if last_style:
            parts.append("\033[0m")
        return "".join(parts)

    def render_surface(self, surface: "Surface") -> None:
        """Draw a full Surface to the terminal using row-level diff."""
        lines = [self._row_to_str(row) for row in surface.rows()]
        curr_size = (surface.width, surface.height)

        if (
            self._prev_frame is None
            or len(self._prev_frame) != len(lines)
            or self._prev_size != curr_size
        ):
            self.clear_screen()
            for idx, line in enumerate(lines, start=1):
                self.move_cursor(idx, 1)
                self._out.write(line)
        else:
            for idx, (old, new) in enumerate(zip(self._prev_frame, lines), start=1):
                if old != new:
                    self.move_cursor(idx, 1)
                    self.erase_line_to_end()
                    self._out.write(new)

        self._prev_frame = lines
        self._prev_size = curr_size

        if self._cursor_pos is not None:
            target = (self._cursor_pos[0] + 1, self._cursor_pos[1] + 1)
            if self._last_cursor != target:
                self.move_cursor(*target)
                self._last_cursor = target
            if not self._cursor_visible:
                self.show_cursor()
                self._cursor_visible = True
        else:
            if self._cursor_visible:
                self.hide_cursor()
                self._cursor_visible = False
            self._last_cursor = None

        self._cursor_pos = None
        self.flush()

    def clear_cache(self) -> None:
        """Invalidate the incremental-render frame cache."""
        self._prev_frame = None
        self._prev_size = None
