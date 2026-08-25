"""
Module: pigit/termui/widgets/label.py
Description: Single-line static text label.
Author: Zev
Date: 2026-08-25
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..component import Component
from ..theme import get_theme
from ..wcwidth_table import pad_by_width, truncate_by_width

if TYPE_CHECKING:
    from ..surface import Surface


class Label(Component):
    """One-line static text; no focus, no input.

    When ``bg`` is set, the full widget width is padded so the background
    covers the row (same contract as :class:`StatusBar`).
    """

    def __init__(
        self,
        text: str = "",
        *,
        fg: tuple[int, int, int] | None = None,
        bg: tuple[int, int, int] | None = None,
        id: str | None = None,
    ) -> None:
        super().__init__(id=id)
        self._text = text
        self._fg = fg
        self._bg = bg

    def set_text(self, text: str) -> None:
        """Replace the displayed text."""
        self._text = text

    def paint(self, surface: Surface) -> None:
        if surface.width <= 0 or surface.height <= 0:
            return
        theme = get_theme()
        fg = self._fg if self._fg is not None else theme.fg_dim
        bg = self._bg
        text = truncate_by_width(self._text, surface.width)
        if bg is not None:
            text = pad_by_width(text, surface.width)
        surface.draw_text_rgb(0, 0, text, fg=fg, bg=bg)
