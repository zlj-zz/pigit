# -*- coding: utf-8 -*-
"""
Module: pigit/termui/_component_layouts.py
Description: Layout container components for the TUI framework.
Author: Zev
Date: 2026-04-20
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal, Optional, Sequence, Union

from ._component_base import Component
from .types import ActionLiteral

if TYPE_CHECKING:
    from ._surface import Surface


class Column(Component):
    """Vertical stack: fixed heights + flex share.

    Children receive geometry from this container; manual ``x, y`` is ignored.
    This component does **not** set ``self.children`` — it uses ``_child_list``
    to maintain ordering and overrides all methods that would otherwise iterate
    over ``self.children`` (``resize``, ``notify``, ``accept``, ``fresh``).
    """

    NAME = "column"

    def __init__(
        self,
        children: Sequence[Component],
        heights: Sequence[Union[int, Literal["flex"]]],
        x: int = 1,
        y: int = 1,
        size: Optional[tuple[int, int]] = None,
    ) -> None:
        super().__init__(x, y, size, children=None)
        self._child_list = list(children)
        for child in self._child_list:
            child.parent = self
        self._heights = list(heights)

    def set_heights(self, heights: Sequence[Union[int, Literal["flex"]]]) -> None:
        if len(heights) != len(self._child_list):
            raise ValueError(
                f"heights length mismatch: expected {len(self._child_list)}, "
                f"got {len(heights)}"
            )
        self._heights = list(heights)

    def resize(self, size: tuple[int, int]) -> None:
        self._size = size
        width, total_h = size
        ox, oy = self.x - 1, self.y - 1

        fixed = sum(h for h in self._heights if h != "flex")
        flex_n = sum(1 for h in self._heights if h == "flex")
        if total_h < fixed:
            flex_h = 0
        else:
            flex_h = max(0, total_h - fixed) // flex_n if flex_n else 0

        # First pass: compute all geometries
        y = oy
        flex_items: list[tuple[int, int]] = []
        geometries: list[tuple[int, int, int, int]] = []
        for i, (child, h) in enumerate(zip(self._child_list, self._heights)):
            if h == "flex":
                flex_items.append((i, flex_h))
                h_val = flex_h
            else:
                remaining = max(0, total_h - (y - oy))
                h_val = min(h, remaining)
            geometries.append((y + 1, oy + 1, width, h_val))
            y += h_val

        # Remainder pixels go to the last flex child (no truncation loss)
        if flex_items and total_h >= fixed:
            remainder = total_h - fixed - flex_h * flex_n
            if remainder > 0:
                last_idx, last_h = flex_items[-1]
                gx, gy, gw, _ = geometries[last_idx]
                geometries[last_idx] = (gx, gy, gw, last_h + remainder)

        # Second pass: apply via child.resize() so subclasses handle their own _size
        for child, (cx, cy, cw, ch) in zip(self._child_list, geometries):
            child.x = cx
            child.y = cy
            if ch > 0:
                child.resize((cw, ch))

    def _render_surface(self, surface: "Surface") -> None:
        for child in self._child_list:
            w, h = child._size
            if w <= 0 or h <= 0:
                continue
            if child.x < 1 or child.y < 1:
                continue
            child._render_surface(
                surface.subsurface(
                    max(0, child.x - 1), max(0, child.y - 1), w, h
                )
            )

    def notify(self, action: ActionLiteral, **data) -> None:
        for child in self._child_list:
            child.update(action, **data)

    def accept(self, action: ActionLiteral, **data) -> None:
        """Broadcast action to all children. Skip leaf components that do not
        override ``accept`` (e.g. ``_PickerHeader``).
        """
        for child in self._child_list:
            if callable(getattr(child, "accept", None)):
                child.accept(action, **data)

    def destroy(self) -> None:
        for child in self._child_list:
            if callable(getattr(child, "destroy", None)):
                child.destroy()

    def fresh(self) -> None:
        pass
