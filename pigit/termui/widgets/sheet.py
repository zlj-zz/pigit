"""
Module: pigit/termui/widgets/sheet.py
Description: Bottom sheet panel (SHEET layer).
Author: Zev
Date: 2026-05-18
"""

from __future__ import annotations

from .._component import Component
from .._surface import Surface, _Subsurface
from ..types import OverlayDispatchResult


class Sheet(Component):
    """Bottom sheet panel, similar to mobile bottom sheet (SHEET layer)."""

    def __init__(
        self,
        child: Component,
        height: int = 8,
        size: tuple[int, int] | None = None,
    ) -> None:
        super().__init__(size=size)
        self._child = child
        child.parent = self
        self._target_height = height
        self._child_dispatch = getattr(child, "dispatch_overlay_key", None)
        self.open = True

    def dispatch_overlay_key(self, key: str) -> OverlayDispatchResult:
        """Forward overlay keys to the child component if supported."""
        if self._child_dispatch is not None:
            return self._child_dispatch(key)
        return OverlayDispatchResult.DROPPED_UNBOUND

    def _render_surface(self, surface: Surface | _Subsurface) -> None:
        if self._size[1] <= 0:
            return
        y = surface.height - self._size[1]
        sub = surface.subsurface(y, 0, self._size[0], self._size[1])
        self._child._render_surface(sub)

    def hide(self) -> None:
        """Close the sheet."""
        self.open = False

    def resize(self, size: tuple[int, int]) -> None:
        """Resize the sheet and its child to the given terminal size."""
        self._size = (size[0], min(self._target_height, size[1] // 2))
        self._child.resize(self._size)
