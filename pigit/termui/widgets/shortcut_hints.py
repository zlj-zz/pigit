"""
Module: pigit/termui/widgets/shortcut_hints.py
Description: Compact key/description hint strip for status bars and footers.
Author: Zev
Date: 2026-08-25
"""

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Callable, Sequence
from typing import TYPE_CHECKING

from .. import palette
from ..component import Component
from ..mouse import MouseButton, MouseEvent, MouseKind
from ..theme import get_theme
from ..wcwidth_table import wcswidth

if TYPE_CHECKING:
    from ..surface import Surface

# One blank column before the first key (separates from a left-hand sibling).
_LEADING_INSET = 1

# Blank columns between two pairs. A click landing there counts as the pair on
# its left, so the strip leaves no dead column between its hints.
_PAIR_GAP = 2


@dataclass(frozen=True)
class _HintSpan:
    """One key/description pair, placed in 0-based surface columns.

    ``[start, end)`` holds the pair's own glyphs and ``key_end`` is where the
    bold key ends and the muted description begins. A pair whose description
    did not fit ends at ``key_end``: only its key was painted.
    """

    index: int
    start: int
    key_end: int
    end: int


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


def _layout_hints(
    pairs: Sequence[tuple[str, str]], *, col: int, max_w: int
) -> list[_HintSpan]:
    """Place every pair that fits, exactly where the strip paints it.

    Hit-testing walks this same layout, so the clickable columns are the
    painted columns by construction rather than by a second copy of the
    arithmetic that could drift from it.

    Args:
        pairs: Key/description pairs, in paint order.
        col: 0-based column the strip starts at.
        max_w: Surface width. Nothing from here on is painted or clickable.

    Returns:
        One span per painted pair. Only the last one can be key-only: a
        description that overruns the width ends the strip, because the paint
        stops there too.
    """
    spans: list[_HintSpan] = []
    cursor = col + _LEADING_INSET
    for i, (key, desc) in enumerate(pairs):
        if i:
            if cursor + _PAIR_GAP > max_w:
                break
            cursor += _PAIR_GAP
        key_end = cursor + wcswidth(key)
        if key_end > max_w:
            break
        desc_w = wcswidth(f" {desc}")
        if key_end + desc_w > max_w:
            spans.append(_HintSpan(i, cursor, key_end, key_end))
            break
        spans.append(_HintSpan(i, cursor, key_end, key_end + desc_w))
        cursor = key_end + desc_w
    return spans


def _pair_at(spans: Sequence[_HintSpan], col: int) -> _HintSpan | None:
    """Return the span covering 0-based *col*, or None if it is past the strip.

    Each pair reaches up to the next pair's first column, which is how the
    blank columns between two hints answer for the hint on their left.
    """
    for i, span in enumerate(spans):
        stop = spans[i + 1].start if i + 1 < len(spans) else span.end
        if span.start <= col < stop:
            return span
    return None


def paint_shortcut_hints(
    surface: Surface,
    pairs: Sequence[tuple[str, str]],
    *,
    row: int = 0,
    col: int = 0,
) -> None:
    """Paint pairs inset by one column from ``col`` (matches :func:`measure_shortcut_hints`)."""
    theme = get_theme()
    for span in _layout_hints(pairs, col=col, max_w=surface.width):
        key, desc = pairs[span.index]
        surface.draw_text_rgb(
            row,
            span.start,
            key,
            fg=theme.fg_primary,
            style_flags=palette.STYLE_BOLD,
        )
        if span.end > span.key_end:
            surface.draw_text_rgb(row, span.key_end, f" {desc}", fg=theme.fg_muted)


class ShortcutHints(Component):
    """Fixed-content shortcut strip (no left context, no separator rule).

    Always fills its rectangle (default ``theme.bg_base``) so prior frame cells
    cannot ghost through when the strip is narrower than the allocated slot.

    With ``on_click`` set the strip is also a mouse target: clicking a pair
    runs it, which is how an action whose keystroke the terminal may never
    deliver stays reachable. The strip looks identical either way -- the label
    already names the action, so a hover state would add nothing to read.
    """

    def __init__(
        self,
        pairs: Sequence[tuple[str, str]],
        *,
        bg: tuple[int, int, int] | None = None,
        id: str | None = None,
        on_click: Callable[[str], None] | None = None,
    ) -> None:
        super().__init__(id=id)
        self._pairs = list(pairs)
        self._bg = bg
        self._on_click = on_click
        self.preferred_width = measure_shortcut_hints(self._pairs)

    def paint(self, surface: Surface) -> None:
        if surface.width <= 0 or surface.height <= 0:
            return
        bg = self._bg if self._bg is not None else get_theme().bg_base
        surface.fill_rect_rgb(0, 0, surface.width, surface.height, bg)
        paint_shortcut_hints(surface, self._pairs, row=0, col=0)

    def handle_mouse(self, event: MouseEvent) -> bool:
        """Run the clicked pair's action, handed ``on_click`` its key label."""
        if self._on_click is None:
            return False
        if event.kind is not MouseKind.PRESS:
            return False
        if event.button is not MouseButton.LEFT:
            return False
        if event.motion:
            # A drag across the strip crosses several pairs; firing each one
            # it passes over would commit on the way to "cancel".
            return False
        span = _pair_at(
            _layout_hints(self._pairs, col=0, max_w=self._size[0]), event.col - 1
        )
        if span is None:
            return False
        self._on_click(self._pairs[span.index][0])
        return True
