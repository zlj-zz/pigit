# -*- coding: utf-8 -*-
"""
Module: pigit/termui/_surface.py
Description: 2-D character buffer for declarative terminal drawing.
Author: Zev
Date: 2026-04-19
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Sequence

from . import palette
from .wcwidth_table import (
    _char_width,
    truncate_by_width,
    wcswidth,
)

if TYPE_CHECKING:
    from ._segment import Segment

# Box-drawing (UTF-8).
_BOX_H = "\u2500"
_BOX_V = "\u2502"
_BOX_TL = "\u250c"
_BOX_TR = "\u2510"
_BOX_BL = "\u2514"
_BOX_BR = "\u2518"


class FlatCell:
    """TrueColor-aware terminal cell with structured style attributes.

    ``fg`` and ``bg`` are RGB tuples. ``style_flags`` controls weight
    and other terminal styles via bitmask.
    When ``ansi_style`` is set, it takes precedence (legacy mode).

    The ``style`` parameter is a backward-compatibility alias for
    ``ansi_style`` so existing ``Cell(char, style="...")`` calls
    continue to work.
    """

    __slots__ = ("char", "fg", "bg", "style_flags", "ansi_style", "_hash")

    def __init__(
        self,
        char: str = " ",
        style: str = "",
        fg: tuple[int, int, int] = palette.DEFAULT_FG,
        bg: tuple[int, int, int] = palette.DEFAULT_BG,
        style_flags: int = 0,
        ansi_style: Optional[str] = None,
        *,
        bold: bool = False,
    ) -> None:
        self.char = char
        self.fg = fg
        self.bg = bg
        # Backward compat: bold=True maps to style_flags with BOLD bit set
        self.style_flags = style_flags | palette.STYLE_BOLD if bold else style_flags
        # Backward compat: 'style' kwarg maps to ansi_style
        self.ansi_style = ansi_style if ansi_style is not None else (style or None)
        self._hash = hash(
            (self.char, self.fg, self.bg, self.style_flags, self.ansi_style)
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, FlatCell):
            return NotImplemented
        return (
            self.char == other.char
            and self.fg == other.fg
            and self.bg == other.bg
            and self.style_flags == other.style_flags
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
            f"style_flags={self.style_flags}, ansi_style={self.ansi_style!r})"
        )


# Backward compatibility: Cell is an alias for FlatCell.
Cell = FlatCell

_BLANK_CELL = FlatCell()
_SPACER_CELL = FlatCell("")


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

    def subsurface(self, row: int, col: int, width: int, height: int) -> "_Subsurface":
        """Return a nested subsurface relative to this one."""
        return _Subsurface(
            self._parent, self._row + row, self._col + col, width, height
        )

    # --- RGB proxy methods ---

    def draw_text_rgb(
        self,
        row: int,
        col: int,
        text: str,
        fg: Optional[tuple[int, int, int]] = None,
        bg: Optional[tuple[int, int, int]] = None,
        style_flags: int = 0,
    ) -> None:
        """Write text with RGB colors at local (row, col), clipped to bounds."""
        if row < 0 or row >= self.height or col >= self.width:
            return
        r, c = self._to_parent(row, col)
        self._parent.draw_text_rgb(r, c, text, fg=fg, bg=bg, style_flags=style_flags)

    def draw_segments(
        self,
        row: int,
        col: int,
        segments: Sequence["Segment"],
    ) -> int:
        """Draw a list of styled segments and return the column after the last one."""
        for seg in segments:
            self.draw_text_rgb(
                row,
                col,
                seg.text,
                fg=seg.fg,
                bg=seg.bg,
                style_flags=seg.style_flags,
            )
            col += wcswidth(seg.text)
        return col

    def fill_rect_rgb(
        self, row: int, col: int, width: int, height: int, bg: tuple[int, int, int]
    ) -> None:
        """Fill a rectangle with an RGB background, clipped to subsurface bounds."""
        clipped = self._clip(row, col, width, height)
        if clipped is None:
            return
        self._parent.fill_rect_rgb(*clipped, bg)

    def draw_box_rgb(
        self,
        row: int,
        col: int,
        width: int,
        height: int,
        fg: tuple[int, int, int],
        bg: tuple[int, int, int] = palette.DEFAULT_BG,
        style_flags: int = 0,
        title: Optional[str] = None,
    ) -> None:
        """Draw an RGB box-drawing border at local (row, col), clipped to bounds."""
        clipped = self._clip(row, col, width, height)
        if clipped is None:
            return
        self._parent.draw_box_rgb(
            *clipped, fg=fg, bg=bg, style_flags=style_flags, title=title
        )

    def draw_vline_rgb(
        self,
        row: int,
        col: int,
        height: int,
        fg: tuple[int, int, int],
        bg: tuple[int, int, int] = palette.DEFAULT_BG,
        style_flags: int = 0,
    ) -> None:
        """Draw a vertical line at local (row, col), clipped to subsurface bounds."""
        if col < 0 or col >= self.width or row >= self.height:
            return
        start = max(row, 0)
        end = min(row + height, self.height)
        visible_height = end - start
        if visible_height <= 0:
            return
        r, c = self._to_parent(start, col)
        self._parent.draw_vline_rgb(
            r, c, visible_height, fg=fg, bg=bg, style_flags=style_flags
        )

    def draw_hline_rgb(
        self,
        row: int,
        col: int,
        width: int,
        fg: tuple[int, int, int],
        bg: tuple[int, int, int] = palette.DEFAULT_BG,
        style_flags: int = 0,
    ) -> None:
        """Draw a horizontal line at local (row, col), clipped to subsurface bounds."""
        if row < 0 or row >= self.height or col >= self.width:
            return
        start = max(col, 0)
        end = min(col + width, self.width)
        visible_width = end - start
        if visible_width <= 0:
            return
        r, c = self._to_parent(row, start)
        self._parent.draw_hline_rgb(
            r, c, visible_width, fg=fg, bg=bg, style_flags=style_flags
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
        blank_row = [_BLANK_CELL] * width
        self._rows: list[list[FlatCell]] = [list(blank_row) for _ in range(height)]

    def __repr__(self) -> str:
        return f"Surface({self.width}x{self.height})"

    def clear(self) -> None:
        """Reset every cell to a blank space."""
        for row in self._rows:
            for i in range(self.width):
                row[i] = _BLANK_CELL

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
        fg: Optional[tuple[int, int, int]] = None,
        bg: Optional[tuple[int, int, int]] = None,
        style_flags: int = 0,
    ) -> None:
        """Write text with explicit RGB foreground and background colors.

        Args:
            row, col: Starting position.
            text: String to write.
            fg: Foreground RGB tuple, or None to use palette.DEFAULT_FG.
            bg: Background RGB tuple, or None to use palette.DEFAULT_BG.
            style_flags: Bitmask of terminal style flags.
        """
        actual_fg = fg if fg is not None else palette.DEFAULT_FG
        actual_bg = bg if bg is not None else palette.DEFAULT_BG

        if row < 0 or row >= self.height or col >= self.width:
            return

        if col < 0:
            # Rare: negative start column; scan char-by-char and clip.
            cur_col = col
            for ch in text:
                if cur_col >= self.width:
                    return
                w = _char_width(ord(ch))
                if cur_col >= 0 and cur_col + w <= self.width:
                    self._rows[row][cur_col] = FlatCell(
                        ch, fg=actual_fg, bg=actual_bg, style_flags=style_flags
                    )
                    if w == 2:
                        self._rows[row][cur_col + 1] = _SPACER_CELL
                cur_col += w
            return

        # Pre-compute width and truncate early to avoid per-char overflow checks.
        if text.isascii():
            total_w = len(text)
            if col + total_w > self.width:
                text = text[: self.width - col]
            for ch in text:
                self._rows[row][col] = FlatCell(
                    ch, fg=actual_fg, bg=actual_bg, style_flags=style_flags
                )
                col += 1
            return

        total_w = wcswidth(text)
        if col + total_w > self.width:
            text = truncate_by_width(text, self.width - col)

        for ch in text:
            if col >= self.width:
                break
            w = _char_width(ord(ch))
            self._rows[row][col] = FlatCell(
                ch, fg=actual_fg, bg=actual_bg, style_flags=style_flags
            )
            if w == 2:
                self._rows[row][col + 1] = _SPACER_CELL
            col += w

    def draw_segments(
        self,
        row: int,
        col: int,
        segments: Sequence["Segment"],
    ) -> int:
        """Draw a list of styled segments and return the column after the last one."""
        for seg in segments:
            self.draw_text_rgb(
                row,
                col,
                seg.text,
                fg=seg.fg,
                bg=seg.bg,
                style_flags=seg.style_flags,
            )
            col += wcswidth(seg.text)
        return col

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

    def draw_box_rgb(
        self,
        row: int,
        col: int,
        width: int,
        height: int,
        fg: tuple[int, int, int],
        bg: tuple[int, int, int] = palette.DEFAULT_BG,
        style_flags: int = 0,
        title: Optional[str] = None,
    ) -> None:
        """Draw a box-drawing border with explicit RGB colors."""
        if width < 2 or height < 2:
            return

        top = _BOX_TL + _BOX_H * (width - 2) + _BOX_TR
        self.draw_text_rgb(row, col, top, fg=fg, bg=bg, style_flags=style_flags)
        for r in range(row + 1, row + height - 1):
            if 0 <= r < self.height:
                if 0 <= col < self.width:
                    self._rows[r][col] = FlatCell(
                        _BOX_V, fg=fg, bg=bg, style_flags=style_flags
                    )
                end_col = col + width - 1
                if 0 <= end_col < self.width:
                    self._rows[r][end_col] = FlatCell(
                        _BOX_V, fg=fg, bg=bg, style_flags=style_flags
                    )
        bottom = _BOX_BL + _BOX_H * (width - 2) + _BOX_BR
        self.draw_text_rgb(
            row + height - 1, col, bottom, fg=fg, bg=bg, style_flags=style_flags
        )

        if title:
            title_text = f" {title[: max(0, width - 4)]} "
            title_text = truncate_by_width(title_text, max(0, width - 2))
            pad = max(0, (width - 2 - wcswidth(title_text)) // 2)
            self.draw_text_rgb(
                row, col + 1 + pad, title_text, fg=fg, bg=bg, style_flags=style_flags
            )

    def draw_vline_rgb(
        self,
        row: int,
        col: int,
        height: int,
        fg: tuple[int, int, int],
        bg: tuple[int, int, int] = palette.DEFAULT_BG,
        style_flags: int = 0,
    ) -> None:
        """Draw a vertical line with RGB colors."""
        cell = FlatCell(_BOX_V, fg=fg, bg=bg, style_flags=style_flags)
        for r in range(row, min(row + height, self.height)):
            if 0 <= r < self.height and 0 <= col < self.width:
                self._rows[r][col] = cell

    def draw_hline_rgb(
        self,
        row: int,
        col: int,
        width: int,
        fg: tuple[int, int, int],
        bg: tuple[int, int, int] = palette.DEFAULT_BG,
        style_flags: int = 0,
    ) -> None:
        """Draw a horizontal line with RGB colors."""
        cell = FlatCell(_BOX_H, fg=fg, bg=bg, style_flags=style_flags)
        for c in range(col, min(col + width, self.width)):
            if 0 <= row < self.height and 0 <= c < self.width:
                self._rows[row][c] = cell

    def rows(self) -> list[list[FlatCell]]:
        """Return the internal row buffers for Renderer output.

        This exposes the 2-D cell grid directly; callers should treat
        each row as read-only and not mutate cells in place.
        """
        return self._rows

    def lines(self) -> list[str]:
        """Flatten buffer to strings for Renderer output."""
        return ["".join(cell.char for cell in row) for row in self._rows]
