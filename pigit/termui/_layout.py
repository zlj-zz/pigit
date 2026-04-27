# -*- coding: utf-8 -*-
"""
Module: pigit/termui/_layout.py
Description: Lightweight layout containers for the terminal UI framework.
Author: Zev
Date: 2026-04-19
"""

from __future__ import annotations

from typing import (
    Literal,
    Protocol,
    Sequence,
    Union,
    runtime_checkable,
)


@runtime_checkable
class SizeModifier(Protocol):
    """Protocol for objects that modify available size and report an offset."""

    def apply(self, available: tuple[int, int]) -> tuple[int, int]:
        """Return the actual (width, height) after modification."""

    def offset(self) -> tuple[int, int]:
        """Return the (top, left) offset introduced by this modifier."""


class Padding:
    """Shrink available space by fixed offsets on each side."""

    def __init__(
        self,
        top: int = 0,
        right: int = 0,
        bottom: int = 0,
        left: int = 0,
    ) -> None:
        self.top = top
        self.right = right
        self.bottom = bottom
        self.left = left

    def apply(self, available: tuple[int, int]) -> tuple[int, int]:
        """Shrink available space by the configured padding."""
        w, h = available
        return max(0, w - self.left - self.right), max(0, h - self.top - self.bottom)

    def offset(self) -> tuple[int, int]:
        """Return the (top, left) offset introduced by this padding."""
        return self.top, self.left


class Border:
    """Reserve 1 cell inward on each side (like a 1-cell thick frame).

    This modifier only reserves space; it does NOT draw any visual border.
    To draw an actual frame, pair this with :class:`BoxFrame`.
    """

    def apply(self, available: tuple[int, int]) -> tuple[int, int]:
        """Shrink available space by 1 cell on each side."""
        w, h = available
        return max(0, w - 2), max(0, h - 2)

    def offset(self) -> tuple[int, int]:
        """Return the (top, left) offset introduced by this border."""
        return 1, 1


def layout_flex(
    sizes: Sequence[Union[int, Literal["flex"]]],
    total: int,
) -> list[int]:
    """Allocate space for fixed + flex children along one axis.

    Fixed sizes are honored (clamped to remaining space). Flex items share
    leftover space evenly via integer division; remainder pixels go to the
    last flex item so no space is wasted and the layout stays stable (only
    one child changes by a small amount when the container resizes).

    Args:
        sizes: Sequence of fixed ints or ``"flex"`` for each child.
        total: Total available pixels along this axis.

    Returns:
        Allocated size in pixels for each child.
    """
    fixed = sum(s for s in sizes if s != "flex")
    flex_indices = [i for i, s in enumerate(sizes) if s == "flex"]
    flex_n = len(flex_indices)

    available = max(0, total - fixed)
    flex_base = available // flex_n if flex_n else 0
    remainder = available - flex_base * flex_n

    result: list[int] = []
    consumed = 0
    for i, s in enumerate(sizes):
        if s == "flex":
            result.append(flex_base)
        else:
            result.append(min(s, max(0, total - consumed)))
        consumed += result[-1]

    if flex_indices and remainder > 0:
        result[flex_indices[-1]] += remainder

    return result
