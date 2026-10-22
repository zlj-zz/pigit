"""
Module: pigit/termui/primitives/frame.py
Description: Reusable bordered frame layout helpers for declarative terminal drawing.
Author: Zev
Date: 2026-08-20
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .. import palette

if TYPE_CHECKING:
    from ..surface import Surface

#: Thumb glyph for the border scrollbar. A right half block is thicker than a
#: rule and lighter than a full block, and it hugs the outer edge -- the side a
#: scrollbar belongs to. The track is the border's own ``│``, so nothing else
#: is drawn and the bar costs no extra column or background.
_SCROLL_THUMB = "▐"


class BoxFrame:
    """Reusable bordered frame — draws a box and reports the content area.

    BoxFrame does **not** draw or manage content; callers own content rendering.
    """

    def __init__(
        self,
        inner_width: int = 0,
        inner_height: int = 0,
        title: str | None = None,
        *,
        fg: tuple[int, int, int] = palette.DEFAULT_FG,
        bg: tuple[int, int, int] = palette.DEFAULT_BG,
        style_flags: int = 0,
    ) -> None:
        self.inner_width = inner_width
        self.inner_height = inner_height
        self.title = title
        self.fg = fg
        self.bg = bg
        self.style_flags = style_flags
        # (first, total, visible) while the owner has scrollable content; None
        # means the frame has nothing to say about it.
        self._scroll: tuple[int, int, int] | None = None

    def set_scroll(self, *, first: int, total: int, visible: int) -> None:
        """Record the scroll window that :meth:`draw` marks on the right border.

        Args:
            first: 0-based index of the first visible item.
            total: Number of items (lines, rows) the content has.
            visible: How many of them the viewport shows.
        """
        self._scroll = (first, total, visible)

    def set_inner_size(self, inner_width: int, inner_height: int) -> None:
        """Update inner dimensions."""
        self.inner_width = inner_width
        self.inner_height = inner_height

    @property
    def outer_width(self) -> int:
        return self.inner_width + 2

    @property
    def outer_height(self) -> int:
        return self.inner_height + 2

    def draw(self, surface: Surface, row: int = 0, col: int = 0) -> None:
        """Draw border (and the scrollbar, if set) onto surface at (row, col)."""
        surface.draw_box_rgb(
            row,
            col,
            self.outer_width,
            self.outer_height,
            fg=self.fg,
            bg=self.bg,
            style_flags=self.style_flags,
            title=self.title,
        )
        self._draw_scrollbar(surface, row, col)

    def _draw_scrollbar(self, surface: Surface, row: int, col: int) -> None:
        """Replace part of the right border with a proportional thumb.

        The track is the border's own ``│`` -- nothing is drawn for it -- so the
        bar cannot change the frame's width or background. Content that fits
        leaves the border untouched.

        Geometry is integer-only. ``first`` is clamped first: a viewport that
        shrank after the content was scrolled can leave the recorded offset past
        the end, and dividing by that would push the thumb outside the frame.
        """
        if self._scroll is None:
            return
        if self.outer_width < 2 or self.outer_height < 2:
            # Same degenerate guard as ``draw_box_rgb``: no border was drawn,
            # so there is no right border column to mark.
            return
        first, total, visible = self._scroll
        track = self.inner_height
        if track <= 0 or visible <= 0 or total <= visible:
            return

        last_first = max(0, total - visible)
        first = min(max(0, first), last_first)
        thumb = max(1, track * visible // total)
        top = (track - thumb) * first // max(1, last_first)

        x = col + self.outer_width - 1
        for i in range(top, top + thumb):
            # Same colour as the border it replaces: the glyph's weight is what
            # marks the thumb, so it follows whatever tone the owner chose --
            # accent on the active diff, dim on an inactive one, primary on
            # Help. A fixed tone would sit darker than a primary border.
            surface.draw_text_rgb(
                row + 1 + i,
                x,
                _SCROLL_THUMB,
                fg=self.fg,
                bg=self.bg,
                style_flags=self.style_flags,
            )

    def content_rect(self, row: int = 0, col: int = 0) -> tuple[int, int, int, int]:
        """Return content area coordinates inside the frame.

        Returns:
            Tuple of (content_row, content_col, inner_width, inner_height).
        """
        return row + 1, col + 1, self.inner_width, self.inner_height
