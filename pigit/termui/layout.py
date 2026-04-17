# -*- coding: utf-8 -*-
"""
Module: pigit/termui/layout.py
Description: Lightweight layout containers for the terminal UI framework.
Author: Zev
Date: 2026-04-17
"""

from __future__ import annotations

from typing import Optional, Protocol, runtime_checkable


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


class FlexRow:
    """Distribute available width among children by flex weights."""

    def __init__(
        self,
        children: list["Component"],
        flexes: Optional[list[int]] = None,
    ) -> None:
        self.children = children
        self.flexes = flexes or [1] * len(children)
        if len(self.flexes) != len(children):
            raise ValueError("flexes length must match children length")

    def resize_children(
        self, available: tuple[int, int], offset: tuple[int, int]
    ) -> None:
        total_w, h = available
        ox, oy = offset
        total_flex = sum(self.flexes)
        if total_flex == 0:
            raise ValueError("total_flex must be > 0")
        if total_w < len(self.children):
            raise ValueError(
                f"available width {total_w} is smaller than child count {len(self.children)}"
            )
        allocated = 0
        for i, (child, flex) in enumerate(zip(self.children, self.flexes)):
            if i == len(self.children) - 1:
                child_w = total_w - allocated
            else:
                child_w = total_w * flex // total_flex
            child_w = max(
                1, min(child_w, total_w - allocated - (len(self.children) - i - 1))
            )
            child.resize((child_w, h))
            child.x = ox + allocated
            child.y = oy
            allocated += child_w


class FlexColumn:
    """Distribute available height among children by flex weights."""

    def __init__(
        self,
        children: list["Component"],
        flexes: Optional[list[int]] = None,
    ) -> None:
        self.children = children
        self.flexes = flexes or [1] * len(children)
        if len(self.flexes) != len(children):
            raise ValueError("flexes length must match children length")

    def resize_children(
        self, available: tuple[int, int], offset: tuple[int, int]
    ) -> None:
        w, total_h = available
        ox, oy = offset
        total_flex = sum(self.flexes)
        if total_flex == 0:
            raise ValueError("total_flex must be > 0")
        if total_h < len(self.children):
            raise ValueError(
                f"available height {total_h} is smaller than child count {len(self.children)}"
            )
        allocated = 0
        for i, (child, flex) in enumerate(zip(self.children, self.flexes)):
            if i == len(self.children) - 1:
                child_h = total_h - allocated
            else:
                child_h = total_h * flex // total_flex
            child_h = max(
                1, min(child_h, total_h - allocated - (len(self.children) - i - 1))
            )
            child.resize((w, child_h))
            child.x = ox
            child.y = oy + allocated
            allocated += child_h


__all__ = [
    "SizeModifier",
    "LayoutEngine",
    "Padding",
    "Border",
    "FlexRow",
    "FlexColumn",
]
