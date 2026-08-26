"""
Module: pigit/termui/containers/exclusive_base.py
Description: Internal base for exclusive-visible containers (not a public widget).
Author: Zev
Date: 2026-08-25
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..component import Component, render_child

if TYPE_CHECKING:
    from ..surface import Surface


class ExclusiveBase(Component):
    """Paint, hit-test, and focus exactly one child (``visible``).

    Subclasses own mount policy and how ``_visible`` changes. Not exported.
    """

    _visible: Component | None = None

    def exclusive_visible_child(self) -> Component | None:
        """Sole painted child; used by :func:`is_on_visible_paint_path`."""
        return self._visible

    @property
    def visible(self) -> Component | None:
        """Child currently painted and hit-tested."""
        return self._visible

    @property
    def focus_child(self) -> Component | None:
        return self._visible

    @property
    def presentation_child(self) -> Component | None:
        return self._visible

    def _id_map(self) -> dict[str, Component]:
        return {c.id: c for c in self.children if c.id}

    def _resolve_direct_child(self, target: Component | str) -> Component | None:
        """Resolve a direct child by instance or ``id`` string."""
        if isinstance(target, Component):
            if target in self.children:
                return target
            return None
        return self._id_map().get(target)

    def resize(self, size: tuple[int, int]) -> None:
        self._size = size
        for child in self.children:
            child.resize(size)

    def paint(self, surface: Surface) -> None:
        if self._visible is not None:
            render_child(self._visible, surface, type(self).__name__)

    def _handle_event(self, key: str) -> bool:
        if self._visible is not None:
            return self._visible._handle_event(key)
        return False

    def _hit_test(self, col: int, row: int) -> tuple[Component, int, int] | None:
        if self._visible is not None:
            return self._visible._hit_test(col, row)
        return None
