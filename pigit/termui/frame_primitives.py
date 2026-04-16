# -*- coding: utf-8 -*-
"""
Module: pigit/termui/frame_primitives.py
Description: Reusable bordered frame layout helpers for declarative terminal drawing.
Author: Zev
Date: 2026-04-16
"""

from __future__ import annotations

from typing import Optional, TYPE_CHECKING

from pigit.termui.wcwidth_table import pad_by_width, truncate_by_width

if TYPE_CHECKING:
    from pigit.termui.surface import Surface


class BoxFrame:
    """Reusable bordered frame layout helper."""

    def __init__(
        self,
        inner_width: int,
        inner_height: int,
        title: Optional[str] = None,
    ) -> None:
        self.inner_width = inner_width
        self.inner_height = inner_height
        self.title = title
        self.outer_width = inner_width + 2
        self.outer_height = inner_height + 2

    def draw_onto(self, surface: "Surface", row: int, col: int) -> None:
        """Draw border onto surface at (row, col)."""
        surface.draw_box(row, col, self.outer_width, self.outer_height, self.title)

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
            text = pad_by_width(truncate_by_width(line, self.inner_width), self.inner_width)
            surface.draw_text(content_row + i, content_col, text)
