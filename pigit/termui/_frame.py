"""
Module: pigit/termui/_frame.py
Description: Reusable bordered frame layout helpers for declarative terminal drawing.
Author: Zev
Date: 2026-04-19
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from . import palette

if TYPE_CHECKING:
    from ._surface import Surface, _Subsurface


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

    def draw(self, surface: Surface | _Subsurface, row: int = 0, col: int = 0) -> None:
        """Draw border onto surface at (row, col)."""
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

    def content_rect(self, row: int = 0, col: int = 0) -> tuple[int, int, int, int]:
        """Return content area coordinates inside the frame.

        Returns:
            Tuple of (content_row, content_col, inner_width, inner_height).
        """
        return row + 1, col + 1, self.inner_width, self.inner_height
