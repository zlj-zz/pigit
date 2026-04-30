# -*- coding: utf-8 -*-
"""
Module: pigit/termui/_renderer.py
Description: Session-bound Renderer for ANSI drawing (1-based row/column).
Author: Zev
Date: 2026-04-19
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Sequence

from . import palette
from ._color import ColorAdapter
from ._surface import FlatCell, Surface

if TYPE_CHECKING:
    from ._session import Session


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
        self._color = ColorAdapter()

    def write(self, text: str) -> None:
        """Write raw text to the terminal output stream."""
        self._out.write(text)

    def flush(self) -> None:
        """Flush the terminal output stream."""
        self._out.flush()

    def clear_screen(self) -> None:
        """Clear the entire screen and move the cursor to the top-left."""
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
        """Hide the terminal cursor."""
        self._out.write("\033[?25l")

    def show_cursor(self) -> None:
        """Show the terminal cursor."""
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

    # ------------------------------------------------------------------ #
    # Row rendering (FlatCell-aware)
    # ------------------------------------------------------------------ #

    def _row_to_str(self, row: list["FlatCell"]) -> str:
        """Convert a row of FlatCells to an ANSI string.

        Dispatches to specialized handlers based on whether the row contains
        legacy ``ansi_style`` cells, RGB cells, or a mix.
        """
        # Determine if any cell actually uses RGB features (non-default colors/bold)
        has_rgb = any(
            cell.char != ""
            and cell.ansi_style is None
            and (
                cell.fg != palette.DEFAULT_FG
                or cell.bg != palette.DEFAULT_BG
                or cell.style_flags
            )
            for cell in row
        )
        has_legacy = any(
            cell.char != "" and cell.ansi_style is not None for cell in row
        )

        if not has_rgb:
            # All cells are legacy or plain default — use legacy renderer
            return self._row_to_str_legacy(row)
        if not has_legacy:
            return self._row_to_str_rgb(row)
        return self._row_to_str_mixed(row)

    def _row_to_str_legacy(self, row: list["FlatCell"]) -> str:
        """Render a row where every cell uses legacy ``ansi_style``."""
        parts = []
        last_style = ""
        for cell in row:
            if cell.char == "":
                continue
            if cell.ansi_style != last_style:
                if last_style:
                    parts.append("\033[0m")
                if cell.ansi_style:
                    parts.append(cell.ansi_style)
                last_style = cell.ansi_style
            parts.append(cell.char)
        if last_style:
            parts.append("\033[0m")
        return "".join(parts)

    def _row_to_str_rgb(self, row: list["FlatCell"]) -> str:
        """Render a row where cells use RGB attributes."""
        parts = []
        last_fg = palette.DEFAULT_FG
        last_bg = palette.DEFAULT_BG
        last_style = 0

        for cell in row:
            if cell.char == "":
                continue
            sgr_parts = []
            if cell.fg != last_fg:
                if cell.fg == palette.DEFAULT_FG:
                    sgr_parts.append("\033[39m")
                else:
                    sgr_parts.append(self._color.fg_sequence(cell.fg))
                last_fg = cell.fg
            if cell.bg != last_bg:
                if cell.bg == palette.DEFAULT_BG:
                    sgr_parts.append("\033[49m")
                else:
                    sgr_parts.append(self._color.bg_sequence(cell.bg))
                last_bg = cell.bg
            if cell.style_flags != last_style:
                if last_style:
                    sgr_parts.append(self._color.reset_style_sequence())
                if cell.style_flags:
                    sgr_parts.append(self._color.style_sequence(cell.style_flags))
                last_style = cell.style_flags

            if sgr_parts:
                parts.extend(sgr_parts)
            parts.append(cell.char)

        if last_fg != palette.DEFAULT_FG or last_bg != palette.DEFAULT_BG or last_style:
            parts.append(self._color.reset_sequence())
        return "".join(parts)

    def _row_to_str_mixed(self, row: list["FlatCell"]) -> str:
        """Render a row containing both legacy and RGB cells."""
        parts = []
        in_legacy = False
        last_fg = palette.DEFAULT_FG
        last_bg = palette.DEFAULT_BG
        last_style = 0

        for cell in row:
            if cell.char == "":
                continue

            if cell.ansi_style is not None:
                # Legacy cell
                if not in_legacy:
                    # Transition from RGB to legacy
                    if (
                        last_fg != palette.DEFAULT_FG
                        or last_bg != palette.DEFAULT_BG
                        or last_style
                    ):
                        parts.append(self._color.reset_sequence())
                        last_fg = palette.DEFAULT_FG
                        last_bg = palette.DEFAULT_BG
                        last_style = 0
                in_legacy = True
                parts.append(cell.ansi_style)
                parts.append(cell.char)
            else:
                # RGB cell
                if in_legacy:
                    # Transition from legacy to RGB: reset terminal state
                    parts.append(self._color.reset_sequence())
                    in_legacy = False
                    last_fg = palette.DEFAULT_FG
                    last_bg = palette.DEFAULT_BG
                    last_style = 0

                sgr_parts = []
                if cell.fg != last_fg:
                    if cell.fg == palette.DEFAULT_FG:
                        sgr_parts.append("\033[39m")
                    else:
                        sgr_parts.append(self._color.fg_sequence(cell.fg))
                    last_fg = cell.fg
                if cell.bg != last_bg:
                    if cell.bg == palette.DEFAULT_BG:
                        sgr_parts.append("\033[49m")
                    else:
                        sgr_parts.append(self._color.bg_sequence(cell.bg))
                    last_bg = cell.bg
                if cell.style_flags != last_style:
                    if last_style:
                        sgr_parts.append(self._color.reset_style_sequence())
                    if cell.style_flags:
                        sgr_parts.append(self._color.style_sequence(cell.style_flags))
                    last_style = cell.style_flags

                parts.extend(sgr_parts)
                parts.append(cell.char)

        # Only emit trailing reset if last active styling is non-default
        if last_fg != palette.DEFAULT_FG or last_bg != palette.DEFAULT_BG or last_style:
            parts.append(self._color.reset_sequence())

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
                # Do NOT call erase_line_to_end() here. In terminals like
                # Ghostty, writing a character to the last column leaves the
                # cursor in a "pending wrap" state; the subsequent EL0
                # (\033[K) can clear that last character, causing full-width
                # rows (e.g. header separator) to appear one column short.
                # Since clear_screen() already blanked the screen, EL0 is
                # redundant on this path anyway.
                self._out.write(line)
        else:
            for idx, (old, new) in enumerate(zip(self._prev_frame, lines), start=1):
                if old != new:
                    self.move_cursor(idx, 1)
                    self._out.write(self._color.reset_sequence())
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
