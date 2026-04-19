# -*- coding: utf-8 -*-
"""
Module: pigit/termui/_component_containers.py
Description: Container components for the TUI framework: TabView and LayoutContainer.
Author: Zev
Date: 2026-04-19
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Callable, Optional

from ._component_base import Component, ComponentError
from .types import ActionLiteral, KeyRouting

if TYPE_CHECKING:
    from ._layout import LayoutEngine
    from ._surface import Surface


def _render_child_to_surface(
    component: "Component", surface: "Surface", log_prefix: str
) -> None:
    w, h = component._size
    if w <= 0 or h <= 0:
        return
    if component.x < 1 or component.y < 1:
        logging.getLogger(__name__).warning(
            "%s %s with invalid 1-based coords (%s, %s)",
            log_prefix,
            component.NAME,
            component.x,
            component.y,
        )
    sub = surface.subsurface(max(0, component.x - 1), max(0, component.y - 1), w, h)
    component._render_surface(sub)


class TabView(Component):
    """Tabbed component stack: only the activated sub-component is rendered."""

    NAME = "tab_view"

    def __init__(
        self,
        children: dict[str, Component],
        x: int = 1,
        y: int = 1,
        size: Optional[tuple[int, int]] = None,
        start_name: Optional[str] = None,
        switch_handle: Optional[Callable[[str], str]] = None,
        key_routing: KeyRouting = "child_first",
    ) -> None:
        super().__init__(x, y, size)
        self.children = children
        for child in children.values():
            child.parent = self
        self.switch_handle = switch_handle
        self._key_routing = key_routing
        self.name = start_name or "main"
        if self.name not in children:
            raise ComponentError(
                "Please set the name, or has a component key is 'main'."
            )
        self._active_child = children[self.name]
        self._active_child.activate()

    def fresh(self):
        pass

    def accept(self, action: ActionLiteral, **data):
        if action == "goto" and (name := data.get("target")) is not None:
            if child := self.switch_child(name):
                child.update(action, **data)
            else:
                logging.getLogger(__name__).warning(f"Not found child: {name}.")
        else:
            raise ComponentError("Not support action of ~TabView.")

    def _render_surface(self, surface: "Surface") -> None:
        if self._active_child is not None:
            _render_child_to_surface(self._active_child, surface, "TabView switch to")

    def _handle_event(self, key: str):
        if self._key_routing == "switch_first" and self.switch_handle:
            self.switch_child(self.switch_handle(key))
        if self._active_child is not None:
            self._active_child._handle_event(key)
        if self._key_routing == "child_first" and self.switch_handle:
            self.switch_child(self.switch_handle(key))

    def switch_child(self, name: str) -> Optional[Component]:
        if name not in self.children:
            return None
        target = self.children[name]
        if target is self._active_child:
            return target
        if self._active_child is not None:
            self._active_child.deactivate()
        target.activate()
        self._active_child = target
        fresh_fn = getattr(target, "fresh", None)
        if callable(fresh_fn):
            try:
                fresh_fn()
            except NotImplementedError:
                pass
        if hasattr(target, "_panel_loaded"):
            target._panel_loaded = True
        return target


class LayoutContainer(Component):
    """Layout-driven container: renders all children via a LayoutEngine."""

    NAME = "layout_container"

    def __init__(
        self,
        layout: "LayoutEngine",
        x: int = 1,
        y: int = 1,
        size: Optional[tuple[int, int]] = None,
    ) -> None:
        super().__init__(x, y, size)
        self._layout = layout
        for child in layout.children:
            child.parent = self

    def fresh(self) -> None:
        pass

    def resize(self, size: tuple[int, int]) -> None:
        super().resize(size)
        self._layout.resize_children(size, offset=(self.x, self.y))

    def _render_surface(self, surface: "Surface") -> None:
        for component in self._layout.children:
            _render_child_to_surface(component, surface, "LayoutContainer child")
