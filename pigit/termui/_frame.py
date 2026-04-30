# -*- coding: utf-8 -*-
"""
Module: pigit/termui/_frame.py
Description: Reusable bordered frame layout helpers for declarative terminal drawing.
Author: Zev
Date: 2026-04-19
"""

from __future__ import annotations

from typing import Optional, TYPE_CHECKING

from .palette import DEFAULT_BG, DEFAULT_FG
from .wcwidth_table import pad_by_width, truncate_by_width

if TYPE_CHECKING:
    from ._surface import Surface


class BoxFrame:
    """Reusable bordered frame layout helper."""

    def __init__(
        self,
        inner_width: int,
        inner_height: int,
        title: Optional[str] = None,
        *,
        fg: tuple[int, int, int] = DEFAULT_FG,
        bg: tuple[int, int, int] = DEFAULT_BG,
        style_flags: int = 0,
    ) -> None:
        self.inner_width = inner_width
        self.inner_height = inner_height
        self.title = title
        self.fg = fg
        self.bg = bg
        self.style_flags = style_flags
        self._recalc_outer()

    def _recalc_outer(self) -> None:
        self.outer_width = self.inner_width + 2
        self.outer_height = self.inner_height + 2

    def set_inner_size(self, inner_width: int, inner_height: int) -> None:
        """Update inner dimensions and recompute outer size."""
        self.inner_width = inner_width
        self.inner_height = inner_height
        self._recalc_outer()

    def draw_onto(self, surface: "Surface", row: int, col: int) -> None:
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

    def draw_content(
        self, surface: "Surface", row: int, col: int, lines: list[str]
    ) -> None:
        """Draw content lines inside the box, clipped to inner dimensions.

        Lines shorter than ``inner_width`` are padded with spaces, and missing
        lines are filled with blank rows so that previous-frame residue does
        not leak through.
        """
        content_row = row + 1
        content_col = col + 1
        padded = list(lines[: self.inner_height])
        while len(padded) < self.inner_height:
            padded.append("")
        for i, line in enumerate(padded):
            text = pad_by_width(
                truncate_by_width(line, self.inner_width), self.inner_width
            )
            surface.draw_text_rgb(
                content_row + i,
                content_col,
                text,
                fg=self.fg,
                bg=self.bg,
                style_flags=self.style_flags,
            )
