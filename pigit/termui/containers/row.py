"""
Module: pigit/termui/containers/row.py
Description: Horizontal stack layout container.
Author: Zev
Date: 2026-05-17
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Literal
from collections.abc import Sequence

from ..component import Component
from .._layout import layout_flex
from ..types import EventType

_logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from ..surface import Surface


class Row(Component):
    """Horizontal stack: fixed widths + flex share.

    Children receive geometry from this container; manual ``x, y`` is ignored.
    """

    def __init__(
        self,
        children: Sequence[Component],
        widths: Sequence[int | Literal["flex"]],
        x: int = 1,
        y: int = 1,
        size: tuple[int, int] | None = None,
        id: str | None = None,
    ) -> None:
        super().__init__(x, y, size, id=id)
        self.children = list(children)
        for child in self.children:
            child.parent = self
        self._widths = list(widths)
        self._last_child_ids: tuple[int, ...] | None = None

    def set_widths(self, widths: Sequence[int | Literal["flex"]]) -> None:
        """Update the width spec and lay out children when the spec or the
        child set changed (a newly attached child must still receive geometry).
        """
        if len(widths) != len(self.children):
            raise ValueError(
                f"widths length mismatch: expected {len(self.children)}, "
                f"got {len(widths)}"
            )
        new_widths = list(widths)
        child_ids = tuple(id(child) for child in self.children)
        if new_widths == self._widths and child_ids == self._last_child_ids:
            return
        self._widths = new_widths
        self._last_child_ids = child_ids
        if self._size is not None:
            self.resize(self._size)

    def activate(self) -> None:
        super().activate()
        for child in self.children:
            child.activate()

    def deactivate(self) -> None:
        super().deactivate()
        for child in self.children:
            child.deactivate()

    def resize(self, size: tuple[int, int]) -> None:
        """Resize the row and lay out children horizontally according to widths."""
        self._size = size
        width, height = size
        widths = layout_flex(self._widths, width)

        offset_h = 0
        for child, w in zip(self.children, widths, strict=True):
            child.x = 1
            child.y = offset_h + 1
            if w > 0:
                child.resize((w, height))
            _logger.debug(
                "Row resize: child=%s x=%s y=%s size=%s",
                type(child).__name__,
                child.x,
                child.y,
                child._size,
            )
            offset_h += w

    def paint(self, surface: Surface) -> None:
        for child in self.children:
            w, h = child._size
            if w <= 0 or h <= 0:
                continue
            if child.x < 1 or child.y < 1:
                continue
            child.paint(
                surface.subsurface(max(0, child.x - 1), max(0, child.y - 1), w, h)
            )

    def accept(self, action: EventType, **data) -> None:
        """Broadcast action to all children. Skip leaf components that do not
        override ``accept``.
        """
        for child in self.children:
            if callable(getattr(child, "accept", None)):
                child.accept(action, **data)
