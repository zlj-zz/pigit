"""
Module: pigit/termui/surface.py
Description: 2-D character buffer for declarative terminal drawing (root and view).
Author: Zev
Date: 2026-08-25
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from collections.abc import Sequence

from . import palette
from .wcwidth_table import (
    _char_width,
    truncate_by_width,
    wcswidth,
)

if TYPE_CHECKING:
    from .segment import Segment

# Box-drawing (UTF-8).
_BOX_H = "\u2500"
_BOX_V = "\u2502"
_BOX_TL = "\u250c"
_BOX_TR = "\u2510"
_BOX_BL = "\u2514"
_BOX_BR = "\u2518"

_ROOT_ONLY = "{method}() is root-only; a view shares the root buffer"


class FlatCell:
    """TrueColor-aware terminal cell with structured style attributes.

    ``fg`` and ``bg`` are RGB tuples. ``style_flags`` controls weight
    and other terminal styles via bitmask.
    """

    __slots__ = ("char", "fg", "bg", "style_flags", "_hash")

    def __init__(
        self,
        char: str = " ",
        fg: tuple[int, int, int] | None = None,
        bg: tuple[int, int, int] | None = None,
        style_flags: int = 0,
    ) -> None:
        self.char = char
        self.fg = fg
        self.bg = bg
        self.style_flags = style_flags
        self._hash: int | None = None

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, FlatCell):
            return NotImplemented
        return (
            self.char == other.char
            and self.fg == other.fg
            and self.bg == other.bg
            and self.style_flags == other.style_flags
        )

    def __hash__(self) -> int:
        if self._hash is None:
            self._hash = hash((self.char, self.fg, self.bg, self.style_flags))
        return self._hash

    def __repr__(self) -> str:
        return (
            f"FlatCell(char={self.char!r}, fg={self.fg}, bg={self.bg}, "
            f"style_flags={self.style_flags})"
        )


_BLANK_CELL = FlatCell()
_SPACER_CELL = FlatCell("")


class Surface:
    """2-D character buffer: one type for root buffer and clipped views.

    Coordinates follow terminal convention: ``row`` is vertical (0-based, top
    to bottom) and ``col`` is horizontal (0-based, left to right).

    A **root** owns ``_rows``. A **view** from ``subsurface`` shares that
    buffer, holds ``_origin_row`` / ``_origin_col`` relative to root, and
    routes every draw/blit through ``_clip_and_translate`` (local clip first,
    then map to root). ``clear`` / ``rows`` / ``lines`` raise on a view.
    ``blit`` requires a root source.
    """

    def __init__(
        self,
        width: int,
        height: int,
        *,
        _root: Surface | None = None,
        _origin_row: int = 0,
        _origin_col: int = 0,
    ) -> None:
        self.width = max(0, width)
        self.height = max(0, height)
        if _root is None:
            self._root = self
            self._origin_row = 0
            self._origin_col = 0
            blank_row = [_BLANK_CELL] * self.width
            self._rows: list[list[FlatCell]] = [
                list(blank_row) for _ in range(self.height)
            ]
        else:
            self._root = _root
            self._origin_row = _origin_row
            self._origin_col = _origin_col
            self._rows = _root._rows

    @property
    def is_root(self) -> bool:
        """True when this surface owns the cell buffer."""
        return self._root is self

    def __repr__(self) -> str:
        if self.is_root:
            return f"Surface({self.width}x{self.height})"
        return (
            f"Surface({self.width}x{self.height} "
            f"@ {self._origin_row},{self._origin_col})"
        )

    def _require_root(self, method: str) -> None:
        if not self.is_root:
            raise RuntimeError(_ROOT_ONLY.format(method=method))

    def _clip_and_translate(
        self, row: int, col: int, width: int, height: int
    ) -> tuple[int, int, int, int] | None:
        """Clip a local rect to this view, then map to root coordinates.

        Negative local origins are clipped away before origin is applied, so
        a view never writes outside its window into the shared root buffer.
        """
        if width <= 0 or height <= 0:
            return None
        src_r0 = max(row, 0)
        src_c0 = max(col, 0)
        src_r1 = min(row + height, self.height)
        src_c1 = min(col + width, self.width)
        if src_r0 >= src_r1 or src_c0 >= src_c1:
            return None
        root_r = self._origin_row + src_r0
        root_c = self._origin_col + src_c0
        cw = src_c1 - src_c0
        ch = src_r1 - src_r0
        root = self._root
        if root_r < 0:
            ch += root_r
            root_r = 0
        if root_c < 0:
            cw += root_c
            root_c = 0
        if root_r >= root.height or root_c >= root.width:
            return None
        cw = min(cw, root.width - root_c)
        ch = min(ch, root.height - root_r)
        if cw <= 0 or ch <= 0:
            return None
        return root_r, root_c, cw, ch

    def clear(self) -> None:
        """Reset every cell to a blank space (root only)."""
        self._require_root("clear")
        for row in self._rows:
            for i in range(self.width):
                row[i] = _BLANK_CELL

    def blit(
        self,
        src: Surface,
        src_row: int,
        src_col: int,
        width: int,
        height: int,
        dst_row: int,
        dst_col: int,
    ) -> None:
        """Copy a region from a root *src* into this surface.

        Destination coordinates are local to this surface and clipped via
        ``_clip_and_translate``. View sources are rejected: ``src_row`` /
        ``src_col`` address the full root grid only.
        """
        if not src.is_root:
            raise RuntimeError("blit() source must be a root Surface")
        clipped = self._clip_and_translate(dst_row, dst_col, width, height)
        if clipped is None:
            return
        root_r, root_c, cw, ch = clipped
        skip_r = max(0, -dst_row)
        skip_c = max(0, -dst_col)
        for r in range(ch):
            srow = src_row + skip_r + r
            drow = root_r + r
            if not (0 <= srow < src.height):
                continue
            for c in range(cw):
                scol = src_col + skip_c + c
                dcol = root_c + c
                if not (0 <= scol < src.width):
                    continue
                self._rows[drow][dcol] = src._rows[srow][scol]

    def subsurface(self, row: int, col: int, width: int, height: int) -> Surface:
        """Return a view with origin flattened onto root (no parent chain)."""
        return Surface(
            width,
            height,
            _root=self._root,
            _origin_row=self._origin_row + row,
            _origin_col=self._origin_col + col,
        )

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
    ) -> Surface:
        """Return a view inset by margins from the given base geometry."""
        return self.subsurface(
            row + margin_top,
            col + margin_left,
            max(0, width - margin_left - margin_right),
            max(0, height - margin_top - margin_bottom),
        )

    def draw_text_rgb(
        self,
        row: int,
        col: int,
        text: str,
        fg: tuple[int, int, int] | None = None,
        bg: tuple[int, int, int] | None = None,
        style_flags: int = 0,
    ) -> None:
        """Write text at local (row, col); each glyph clipped via ``_clip_and_translate``.

        A glyph writes only when its full cell span survives the clip (no
        half-wide characters). Glyphs that start left of the view are skipped;
        drawing stops once the cursor passes the right edge.
        """
        cur_col = col
        for ch in text:
            w = _char_width(ord(ch)) if not ch.isascii() else 1
            if cur_col >= self.width:
                return
            clipped = self._clip_and_translate(row, cur_col, w, 1)
            if clipped is not None:
                root_r, root_c, cw, _ = clipped
                if cw == w:
                    self._rows[root_r][root_c] = FlatCell(
                        ch, fg=fg, bg=bg, style_flags=style_flags
                    )
                    if w == 2:
                        self._rows[root_r][root_c + 1] = _SPACER_CELL
            cur_col += w

    def draw_segments(
        self,
        row: int,
        col: int,
        segments: Sequence[Segment],
    ) -> int:
        """Draw styled segments and return the column after the last one."""
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
        self,
        row: int,
        col: int,
        width: int,
        height: int,
        bg: tuple[int, int, int] | None = None,
    ) -> None:
        """Fill a rectangle with spaces (clipped to this view)."""
        clipped = self._clip_and_translate(row, col, width, height)
        if clipped is None:
            return
        root_r, root_c, cw, ch = clipped
        cell = FlatCell(" ", bg=bg)
        for r in range(root_r, root_r + ch):
            for c in range(root_c, root_c + cw):
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
        title: str | None = None,
    ) -> None:
        """Draw a box-drawing border; geometry clipped per-cell via draw_text_rgb."""
        if width < 2 or height < 2:
            return
        top = _BOX_TL + _BOX_H * (width - 2) + _BOX_TR
        self.draw_text_rgb(row, col, top, fg=fg, bg=bg, style_flags=style_flags)
        for r in range(row + 1, row + height - 1):
            self.draw_text_rgb(r, col, _BOX_V, fg=fg, bg=bg, style_flags=style_flags)
            self.draw_text_rgb(
                r, col + width - 1, _BOX_V, fg=fg, bg=bg, style_flags=style_flags
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
        """Draw a vertical line clipped to this view."""
        clipped = self._clip_and_translate(row, col, 1, height)
        if clipped is None:
            return
        root_r, root_c, _, ch = clipped
        cell = FlatCell(_BOX_V, fg=fg, bg=bg, style_flags=style_flags)
        for r in range(root_r, root_r + ch):
            self._rows[r][root_c] = cell

    def draw_hline_rgb(
        self,
        row: int,
        col: int,
        width: int,
        fg: tuple[int, int, int],
        bg: tuple[int, int, int] | None = palette.DEFAULT_BG,
        style_flags: int = 0,
    ) -> None:
        """Draw a horizontal line clipped to this view."""
        clipped = self._clip_and_translate(row, col, width, 1)
        if clipped is None:
            return
        root_r, root_c, cw, _ = clipped
        cell = FlatCell(_BOX_H, fg=fg, bg=bg, style_flags=style_flags)
        for c in range(root_c, root_c + cw):
            self._rows[root_r][c] = cell

    def rows(self) -> list[list[FlatCell]]:
        """Return the root cell grid for Renderer output (root only)."""
        self._require_root("rows")
        return self._rows

    def lines(self) -> list[str]:
        """Flatten the root buffer to strings (root only)."""
        self._require_root("lines")
        return ["".join(cell.char for cell in row) for row in self._rows]
