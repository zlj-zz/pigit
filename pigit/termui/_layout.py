# -*- coding: utf-8 -*-
"""
Module: pigit/termui/_layout.py
Description: Lightweight layout containers for the terminal UI framework.
Author: Zev
Date: 2026-04-19
"""

from __future__ import annotations

from typing import Optional, Protocol, runtime_checkable, TYPE_CHECKING

if TYPE_CHECKING:
    from ._component_base import Component


@runtime_checkable
class SizeModifier(Protocol):
    def apply(self, available: tuple[int, int]) -> tuple[int, int]:
        """Return the actual (width, height) after modification."""

    def offset(self) -> tuple[int, int]:
        """Return the (top, left) offset introduced by this modifier."""


@runtime_checkable
class LayoutEngine(Protocol):
    def resize_children(
        self, available: tuple[int, int], offset: tuple[int, int]
    ) -> None:
        """Resize all managed children within the available space.

        ``offset`` is the parent container's (x, y) in screen 1-based
        coordinates; children x/y must be set relative to the screen.
        """


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
        w, h = available
        return max(0, w - self.left - self.right), max(0, h - self.top - self.bottom)

    def offset(self) -> tuple[int, int]:
        return self.top, self.left


class Border:
    """Reserve 1 cell inward on each side (like a 1-cell thick frame).

    This modifier only reserves space; it does NOT draw any visual border.
    To draw an actual frame, pair this with :class:`BoxFrame`.
    """

    def apply(self, available: tuple[int, int]) -> tuple[int, int]:
        w, h = available
        return max(0, w - 2), max(0, h - 2)

    def offset(self) -> tuple[int, int]:
        return 1, 1


__all__ = [
    "SizeModifier",
    "LayoutEngine",
    "Padding",
    "Border",
]
