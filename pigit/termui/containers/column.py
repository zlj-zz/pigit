"""
Module: pigit/termui/containers/column.py
Description: Vertical stack layout container.
Author: Zev
Date: 2026-05-17
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Literal
from collections.abc import Sequence

from .._component import Component
from .._layout import layout_flex
from .._runtime_context import request_render
from ..types import ActionEventType

_logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from .._surface import Surface, _Subsurface


class Column(Component):
    """Vertical stack: fixed heights + flex share.

    Children receive geometry from this container; manual ``x, y`` is ignored.

    When ``focus_index`` is set, Column manages ``presented_child`` and
    ``event_target`` so the active child receives events and external queries
    (help, inspector) penetrate transparently. Tab cycles focus between children.
    """

    def __init__(
        self,
        children: Sequence[Component],
        heights: Sequence[int | Literal["flex"]],
        focus_index: int | None = None,
        x: int = 1,
        y: int = 1,
        size: tuple[int, int] | None = None,
        id: str | None = None,
    ) -> None:
        super().__init__(x, y, size, id=id)
        self.children = list(children)
        for child in self.children:
            child.parent = self
        self._heights = list(heights)
        self._focus_index = focus_index

    def set_heights(self, heights: Sequence[int | Literal["flex"]]) -> None:
        """Update the height spec for each child and validate the length.

        If this component already has a size, the layout is recalculated
        automatically so callers do not need to call ``resize`` manually.
        """
        if len(heights) != len(self.children):
            raise ValueError(
                f"heights length mismatch: expected {len(self.children)}, "
                f"got {len(heights)}"
            )
        new_heights = list(heights)
        if new_heights == self._heights:
            return
        self._heights = new_heights
        if self._size is not None:
            self.resize(self._size)

    def resize(self, size: tuple[int, int]) -> None:
        """Resize the column and lay out children vertically according to heights."""
        self._size = size
        width, total_h = size
        heights = layout_flex(self._heights, total_h)

        offset_v = 0
        for child, h in zip(self.children, heights, strict=True):
            child.x = offset_v + 1
            child.y = 1
            if h > 0:
                child.resize((width, h))
            _logger.debug(
                "Column resize: child=%s x=%s y=%s size=%s",
                type(child).__name__,
                child.x,
                child.y,
                child._size,
            )
            offset_v += h

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

    def _focused_child(self) -> Component | None:
        """Return the currently focused child, or ``None``."""
        if self._focus_index is not None:
            if 0 <= self._focus_index < len(self.children):
                return self.children[self._focus_index]
        return None

    @property
    def presented_child(self) -> Component | None:
        """Return the focused child when ``focus_index`` is set."""
        return self._focused_child()

    @property
    def event_target(self) -> Component | None:
        """Forward events to the focused child when ``focus_index`` is set."""
        return self._focused_child()

    def handle_key(self, key: str) -> bool:
        """Cycle focus on Tab when ``focus_index`` is set."""
        if self._focus_index is not None and key == "tab":
            self.focus_next()
            return True
        return False

    def focus_next(self) -> None:
        """Cycle focus to the next child panel."""
        if self._focus_index is None or not self.children:
            return
        old_child = self._focused_child()
        self._focus_index = (self._focus_index + 1) % len(self.children)
        new_child = self._focused_child()
        _logger.debug(
            "[FOCUS] focus_next: old=%s new=%s focus_index=%s",
            type(old_child).__name__ if old_child else None,
            type(new_child).__name__ if new_child else None,
            self._focus_index,
        )
        if old_child is not None and old_child is not new_child:
            old_child.deactivate()
        if new_child is not None and new_child is not old_child:
            new_child.activate()
        self.emit(ActionEventType.mode_changed, mode="")
        self.emit(ActionEventType.selection_changed)
        request_render()

    def activate(self) -> None:
        super().activate()
        child = self._focused_child()
        if child is not None:
            child.activate()
        else:
            for child in self.children:
                child.activate()

    def deactivate(self) -> None:
        super().deactivate()
        for child in self.children:
            child.deactivate()

    def accept(self, action: ActionEventType, **data) -> None:
        """Broadcast action to all children. Skip leaf components that do not
        override ``accept`` (e.g. ``_PickerHeader``).
        """
        for child in self.children:
            if callable(getattr(child, "accept", None)):
                child.accept(action, **data)
