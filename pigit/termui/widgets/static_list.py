"""
Module: pigit/termui/widgets/static_list.py
Description: Read-only multi-line list without cursor or selection.
Author: Zev
Date: 2026-08-25
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import TYPE_CHECKING

from ..component import Component
from ..theme import get_theme
from ..wcwidth_table import pad_by_width, truncate_by_width, wcswidth

if TYPE_CHECKING:
    from ..surface import Surface

RowStyle = Callable[[int, str], tuple[int, int, int] | None]


def _fit_row(text: str, width: int) -> str:
    """Truncate to display width; append ellipsis when clipped."""
    if width <= 0:
        return ""
    if wcswidth(text) <= width:
        return text
    if width == 1:
        return "\u2026"
    return truncate_by_width(text, width - 1) + "\u2026"


class StaticList(Component):
    """Paint rows of text; optional per-row foreground via ``row_style``.

    When ``bg`` is set, the full widget rectangle is filled first so short or
    missing rows do not leave terminal-default cells (same idea as StatusBar).
    """

    def __init__(
        self,
        rows: Sequence[str] | None = None,
        *,
        empty_text: str = "",
        row_style: RowStyle | None = None,
        fg: tuple[int, int, int] | None = None,
        bg: tuple[int, int, int] | None = None,
        id: str | None = None,
    ) -> None:
        super().__init__(id=id)
        self._rows = list(rows) if rows else []
        self._empty_text = empty_text
        self._row_style = row_style
        self._fg = fg
        self._bg = bg

    def set_rows(self, rows: Sequence[str]) -> None:
        """Replace all row strings."""
        self._rows = list(rows)

    def paint(self, surface: Surface) -> None:
        if surface.width <= 0 or surface.height <= 0:
            return
        theme = get_theme()
        default_fg = self._fg if self._fg is not None else theme.fg_dim
        bg = self._bg
        if bg is not None:
            surface.fill_rect_rgb(0, 0, surface.width, surface.height, bg)

        if not self._rows:
            if self._empty_text:
                text = _fit_row(self._empty_text, surface.width)
                if bg is not None:
                    text = pad_by_width(text, surface.width)
                surface.draw_text_rgb(0, 0, text, fg=default_fg, bg=bg)
            return

        for i, row in enumerate(self._rows[: surface.height]):
            fg = default_fg
            if self._row_style is not None:
                styled = self._row_style(i, row)
                if styled is not None:
                    fg = styled
            text = _fit_row(row, surface.width)
            if bg is not None:
                text = pad_by_width(text, surface.width)
            surface.draw_text_rgb(i, 0, text, fg=fg, bg=bg)
