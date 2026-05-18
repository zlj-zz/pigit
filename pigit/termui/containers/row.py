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

from .._component import Component
from .._layout import layout_flex
from ..types import ActionEventType

_logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from .._surface import Surface, _Subsurface


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

    def set_widths(self, widths: Sequence[int | Literal["flex"]]) -> None:
        """Update the width spec for each child and validate the length.

        If this component already has a size, the layout is recalculated
        automatically so callers do not need to call ``resize`` manually.
        """
        if len(widths) != len(self.children):
            raise ValueError(
                f"widths length mismatch: expected {len(self.children)}, "
                f"got {len(widths)}"
            )
        new_widths = list(widths)
        if new_widths == self._widths:
            return
        self._widths = new_widths
        if self._size is not None:
            self.resize(self._size)

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

    def _render_surface(self, surface: Surface | _Subsurface) -> None:
        for child in self.children:
            w, h = child._size
            if w <= 0 or h <= 0:
                continue
            if child.x < 1 or child.y < 1:
                continue
            child._render_surface(
                surface.subsurface(max(0, child.x - 1), max(0, child.y - 1), w, h)
            )

    def accept(self, action: ActionEventType, **data) -> None:
        """Broadcast action to all children. Skip leaf components that do not
        override ``accept``.
        """
        for child in self.children:
            if callable(getattr(child, "accept", None)):
                child.accept(action, **data)
