"""
Module: pigit/termui/widgets/shortcut_hints.py
Description: Compact key/description hint strip for status bars and footers.
Author: Zev
Date: 2026-08-25
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

from .. import palette
from ..component import Component
from ..theme import get_theme
from ..wcwidth_table import wcswidth

if TYPE_CHECKING:
    from ..surface import Surface

# One blank column before the first key (separates from a left-hand sibling).
_LEADING_INSET = 1


def _pairs_display_width(pairs: Sequence[tuple[str, str]]) -> int:
    parts: list[str] = []
    for i, (key, desc) in enumerate(pairs):
        if i:
            parts.append("  ")
        parts.append(f"{key} {desc}")
    return wcswidth("".join(parts))


def measure_shortcut_hints(pairs: Sequence[tuple[str, str]]) -> int:
    """Intrinsic width: leading inset plus joined key/desc pairs."""
    return _LEADING_INSET + _pairs_display_width(pairs)


def paint_shortcut_hints(
    surface: Surface,
    pairs: Sequence[tuple[str, str]],
    *,
    row: int = 0,
    col: int = 0,
) -> None:
    """Paint pairs inset by one column from ``col`` (matches :func:`measure_shortcut_hints`)."""
    theme = get_theme()
    max_w = surface.width
    cursor = col + _LEADING_INSET
    for i, (key, desc) in enumerate(pairs):
        if i > 0:
            gap = "  "
            if cursor + wcswidth(gap) > max_w:
                break
            surface.draw_text_rgb(row, cursor, gap, fg=theme.fg_muted)
            cursor += wcswidth(gap)
        if cursor + wcswidth(key) > max_w:
            break
        surface.draw_text_rgb(
            row,
            cursor,
            key,
            fg=theme.fg_primary,
            style_flags=palette.STYLE_BOLD,
        )
        cursor += wcswidth(key)
        desc_text = f" {desc}"
        if cursor + wcswidth(desc_text) > max_w:
            break
        surface.draw_text_rgb(row, cursor, desc_text, fg=theme.fg_muted)
        cursor += wcswidth(desc_text)


class ShortcutHints(Component):
    """Fixed-content shortcut strip (no left context, no separator rule).

    Always fills its rectangle (default ``theme.bg_base``) so prior frame cells
    cannot ghost through when the strip is narrower than the allocated slot.
    """

    def __init__(
        self,
        pairs: Sequence[tuple[str, str]],
        *,
        bg: tuple[int, int, int] | None = None,
        id: str | None = None,
    ) -> None:
        super().__init__(id=id)
        self._pairs = list(pairs)
        self._bg = bg
        self.preferred_width = measure_shortcut_hints(self._pairs)

    def paint(self, surface: Surface) -> None:
        if surface.width <= 0 or surface.height <= 0:
            return
        bg = self._bg if self._bg is not None else get_theme().bg_base
        surface.fill_rect_rgb(0, 0, surface.width, surface.height, bg)
        paint_shortcut_hints(surface, self._pairs, row=0, col=0)
