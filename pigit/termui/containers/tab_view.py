"""
Module: pigit/termui/containers/tab_view.py
Description: Tabbed component stack container.
Author: Zev
Date: 2026-05-17
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from collections.abc import Callable, Sequence

from .._component import Component, _render_child_to_surface
from .._runtime_context import get_focus_manager
from ..types import ActionEventType

_logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from .._surface import Surface, _Subsurface


class TabView(Component):
    """Tabbed component stack: only the activated sub-component is rendered."""

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

    def _id_map(self) -> dict[str, Component]:
        return {c.id: c for c in self.children if c.id}

    def _resolve_start(self) -> None:
        """Resolve start id to component reference after children are ready."""
        id_map = self._id_map()

        resolved = id_map.get(self._start_id) if self._start_id else None
        if resolved is not None:
            self._active = resolved
        else:
            if self._start_id:
                _logger.warning(
                    "TabView start id '%s' not found, falling back to first child",
                    self._start_id,
                )
            self._active = self.children[0]
        self._active.activate()
        fm = get_focus_manager()
        if fm is not None:
            fm.set_focus_chain(self._active)

    @property
    def active(self) -> Component | None:
        """Return the currently active child panel."""
        return self._active

    def route_to(self, id: str) -> Component | None:
        """Switch to the child component with the given id."""
        resolved = self._id_map().get(id)
        if resolved is None:
            return None
        if resolved is self._active:
            return resolved
        # Force full redraw; previous panel content would otherwise ghost
        # through incremental row diff.
        r = self.renderer
        if r is not None:
            r.clear_cache()
        if self._active is not None:
            self._active.deactivate()
        resolved.activate()
        self._active = resolved
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
            fm.set_focus_chain(resolved)
        return resolved

    def on_event(self, action: ActionEventType, **data) -> bool:
        """Route goto to accept; let all other events bubble up."""
        if action is ActionEventType.goto:
            self.accept(action, **data)
            return True
        return False

    def accept(self, action: ActionEventType, **data):
        """Handle a goto action by routing to the target child."""
        if action is ActionEventType.goto:
            target = data.get("target")
            target_id = None
            if isinstance(target, str):
                target_id = target
            elif (
                isinstance(target, Component) and target in self.children and target.id
            ):
                target_id = target.id
            if target_id:
                self.route_to(target_id)
                if self._active is not None:
                    self._active.update(action, **data)
            else:
                _logger.warning(
                    "TabView.goto: target %r not found in children",
                    target,
                )
            return
        _logger.warning("TabView: unsupported action %r", action)

    def resize(self, size: tuple[int, int]) -> None:
        """Resize the container and propagate the new size to all children."""
        self._size = size
        for child in self.children:
            child.resize(size)

    def _render_surface(self, surface: Surface | _Subsurface) -> None:
        if self._active is not None:
            _render_child_to_surface(self._active, surface, "TabView")

    def _handle_event(self, key: str) -> bool:
        if self._active is not None:
            return self._active._handle_event(key)
        return False
