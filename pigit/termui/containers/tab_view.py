"""
Module: pigit/termui/containers/tab_view.py
Description: Tabbed component stack with cold exclusive visibility.
Author: Zev
Date: 2026-05-17
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence

from ..component import Component, resolve_focus_leaf
from .._runtime_context import get_focus_manager
from ..types import EventType, EVT_GOTO
from .exclusive_base import ExclusiveBase

_logger = logging.getLogger(__name__)


class TabView(ExclusiveBase):
    """Tabbed stack: only the visible child is painted (cold unmount on switch)."""

    def __init__(
        self,
        children: Sequence[Component],
        start: str | None = None,
        on_switch: Callable[[Component], None] | None = None,
        x: int = 1,
        y: int = 1,
        size: tuple[int, int] | None = None,
        id: str | None = None,
    ) -> None:
        super().__init__(x, y, size, id=id)

        self._on_switch = on_switch
        self.children = list(children)
        for child in self.children:
            if child.parent is not None and child.parent is not self:
                _logger.warning("Reparenting %s to TabView", type(child).__name__)
            child.parent = self

        self._start_id = start
        self._resolve_start()

    def _resolve_start(self) -> None:
        """Resolve start id to component reference after children are ready."""
        id_map = self._id_map()

        resolved = id_map.get(self._start_id) if self._start_id else None
        if resolved is not None:
            self._visible = resolved
        else:
            if self._start_id:
                _logger.warning(
                    "TabView start id '%s' not found, falling back to first child",
                    self._start_id,
                )
            self._visible = self.children[0]
        self._visible.mount()
        fm = get_focus_manager()
        if fm is not None:
            fm.set_focus_chain(resolve_focus_leaf(self._visible))

    def mount(self) -> None:
        super().mount()
        if self._visible is not None:
            self._visible.mount()

    def unmount(self) -> None:
        if self._visible is not None:
            self._visible.unmount()
        super().unmount()

    def route_to(self, target: str | Component) -> Component | None:
        """Switch to the child identified by id string or component reference.

        When given a Component, resolves it to a child id via the tree.
        """
        tid: str | None
        if isinstance(target, Component):
            tid = self._resolve_target_id(target)
        else:
            tid = target
        if tid is None:
            return None
        resolved = self._id_map().get(tid)
        if resolved is None:
            return None
        if resolved is self._visible:
            return resolved
        # Force full redraw; previous panel content would otherwise ghost
        # through incremental row diff.
        r = self.renderer
        if r is not None:
            r.clear_cache()
        if self._visible is not None:
            self._visible.unmount()
        resolved.mount()
        self._visible = resolved
        fresh_fn = getattr(resolved, "refresh", None)
        if callable(fresh_fn):
            try:
                fresh_fn()
            except NotImplementedError:
                pass
            except Exception:
                _logger.exception("refresh() failed for %s", type(resolved).__name__)
        if hasattr(resolved, "_panel_loaded"):
            setattr(resolved, "_panel_loaded", True)
        if self._on_switch is not None:
            self._on_switch(resolved)
        fm = get_focus_manager()
        if fm is not None:
            fm.set_focus_chain(resolve_focus_leaf(resolved))
        return resolved

    def _resolve_target_id(self, target) -> str | None:
        """Resolve a goto target to a child id string."""
        if isinstance(target, str):
            return target
        if isinstance(target, Component):
            if target in self.children and target.id:
                return target.id
            node: Component | None = target.parent
            while node is not None and node is not self:
                if node in self.children and node.id:
                    return node.id
                node = node.parent
        return None

    def accept(self, action: EventType, **data):
        """Handle a goto action by routing to the target child."""
        if action is EVT_GOTO:
            target = data.get("target")
            target_id = self._resolve_target_id(target)
            if target_id:
                self.route_to(target_id)
                if self._visible is not None:
                    self._visible.update(action, **data)
            else:
                _logger.warning(
                    "TabView.goto: target %r not found in children",
                    target,
                )
            return
        _logger.warning("TabView: unsupported action %r", action)
