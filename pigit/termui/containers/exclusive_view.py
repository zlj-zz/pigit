"""
Module: pigit/termui/containers/exclusive_view.py
Description: Exclusive view; show swaps paint/focus without unmounting siblings.
Author: Zev
Date: 2026-08-25
"""

from __future__ import annotations

import logging
from collections.abc import Sequence

from ..component import (
    Component,
    mount_children,
    resolve_focus_leaf,
    resolve_presentation_leaf,
    unmount_children,
)
from .._runtime_context import get_focus_manager, request_render
from ..types import EVT_SELECTION_CHANGED
from .exclusive_base import ExclusiveBase

_logger = logging.getLogger(__name__)


class ExclusiveView(ExclusiveBase):
    """Mutually exclusive view: all children stay mounted; only one is visible.

    Unlike :class:`TabView` (cold hide via unmount on switch), ``show`` never
    unmounts the hidden child. Mount children when this container itself is
    mounted — not in ``__init__``.
    """

    def __init__(
        self,
        children: Sequence[Component],
        *,
        visible: Component | str | None = None,
        id: str | None = None,
    ) -> None:
        super().__init__(id=id)
        if not children:
            raise ValueError("ExclusiveView requires at least one child")
        self.children = list(children)
        for child in self.children:
            if child.parent is not None and child.parent is not self:
                _logger.warning("Reparenting %s to ExclusiveView", type(child).__name__)
            child.parent = self
        self._visible = self._resolve_initial_visible(visible)

    def _resolve_initial_visible(self, visible: Component | str | None) -> Component:
        if visible is None:
            return self.children[0]
        resolved = self._resolve_direct_child(visible)
        if resolved is None:
            raise ValueError(f"ExclusiveView initial visible not found: {visible!r}")
        return resolved

    def show(self, target: Component | str) -> Component | None:
        """Make ``target`` visible without unmounting siblings.

        Args:
            target: Direct child component or child ``id`` string.

        Returns:
            The visible child, or ``None`` if ``target`` could not be resolved.
        """
        resolved = self._resolve_direct_child(target)
        if resolved is None:
            _logger.warning(
                "ExclusiveView.show: target %r not found in children", target
            )
            return None
        previous = self._visible
        same = resolved is previous
        self._visible = resolved
        if not same and previous is not None:
            previous.on_hide()
        self._focus_visible()
        if not same:
            self.emit(
                EVT_SELECTION_CHANGED,
                active=resolve_presentation_leaf(self._visible),
            )
        request_render()
        return self._visible

    def _focus_visible(self) -> None:
        fm = get_focus_manager()
        if fm is None or self._visible is None:
            return
        fm.set_focus_chain(resolve_focus_leaf(self._visible))

    def mount(self) -> None:
        super().mount()
        mount_children(self)

    def unmount(self) -> None:
        unmount_children(self)
        super().unmount()
