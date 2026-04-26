# -*- coding: utf-8 -*-
"""
Module: pigit/termui/_component_layouts.py
Description: Layout container components for the TUI framework.
Author: Zev
Date: 2026-04-20
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Callable, Literal, Optional, Sequence, Union

from ._component_base import Component, ComponentError, _render_child_to_surface
from ._layout import layout_flex
from .types import ActionLiteral

_logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from ._surface import Surface


class TabView(Component):
    """Tabbed component stack: only the activated sub-component is rendered."""

    def __init__(
        self,
        children: list[Component],
        shortcuts: Optional[dict[str, Component]] = None,
        start: Optional[Component] = None,
        on_switch: Optional[Callable[[Component], None]] = None,
        x: int = 1,
        y: int = 1,
        size: Optional[tuple[int, int]] = None,
    ) -> None:
        super().__init__(x, y, size)

        self._on_switch = on_switch
        self.children = list(children)
        for child in self.children:
            if child.parent is not None and child.parent is not self:
                _logger.warning("Reparenting %s to TabView", type(child).__name__)
            child.parent = self

        self._shortcuts = dict(shortcuts) if shortcuts else {}
        for key, panel in self._shortcuts.items():
            if panel not in self.children:
                raise ComponentError(
                    f"shortcuts['{key}'] -> {type(panel).__name__} not in children"
                )

        if not self.children:
            raise ComponentError("children cannot be empty.")
        if start is None:
            start = self.children[0]
        if start not in self.children:
            raise ComponentError(
                f"start {type(start).__name__} not in children. "
                f"Available: {[type(c).__name__ for c in self.children]}."
            )
        self._active = start
        self._active.activate()

    @property
    def active(self) -> Optional[Component]:
        """Return the currently active child panel."""
        return self._active

    def route_to(self, target: Component) -> Optional[Component]:
        """Switch to the given child component."""
        if target not in self.children:
            return None
        if target is self._active:
            return target
        # Force full redraw; previous panel content would otherwise ghost
        # through incremental row diff.
        r = self.renderer
        if r is not None:
            r.clear_cache()
        if self._active is not None:
            self._active.deactivate()
        target.activate()
        self._active = target
        fresh_fn = getattr(target, "fresh", None)
        if callable(fresh_fn):
            try:
                fresh_fn()
            except NotImplementedError:
                pass
            except Exception:
                _logger.exception("fresh() failed for %s", type(target).__name__)
        if hasattr(target, "_panel_loaded"):
            target._panel_loaded = True
        if self._on_switch is not None:
            self._on_switch(target)
        return target

    def accept(self, action: ActionLiteral, **data):
        if action is ActionLiteral.goto:
            target = data.get("target")
            if isinstance(target, Component) and target in self.children:
                self.route_to(target)
                self._active.update(action, **data)
            else:
                _logger.warning(
                    "TabView.goto: target %r not found in children",
                    target,
                )
            return
        _logger.warning("TabView: unsupported action %r", action)

    def resize(self, size: tuple[int, int]) -> None:
        self._size = size
        for child in self.children:
            child.resize(size)

    def _render_surface(self, surface: "Surface") -> None:
        if self._active is not None:
            _render_child_to_surface(self._active, surface, "TabView")

    def _handle_event(self, key: str):
        if self._shortcuts:
            panel = self._shortcuts.get(key)
            if panel is not None and panel in self.children:
                if panel is not self._active:
                    self.route_to(panel)
                    return
        if self._active is not None:
            self._active._handle_event(key)


class Column(Component):
    """Vertical stack: fixed heights + flex share.

    Children receive geometry from this container; manual ``x, y`` is ignored.
    """

    def __init__(
        self,
        children: Sequence[Component],
        heights: Sequence[Union[int, Literal["flex"]]],
        x: int = 1,
        y: int = 1,
        size: Optional[tuple[int, int]] = None,
    ) -> None:
        super().__init__(x, y, size)
        self.children = list(children)
        for child in self.children:
            child.parent = self
        self._heights = list(heights)

    def set_heights(self, heights: Sequence[Union[int, Literal["flex"]]]) -> None:
        if len(heights) != len(self.children):
            raise ValueError(
                f"heights length mismatch: expected {len(self.children)}, "
                f"got {len(heights)}"
            )
        self._heights = list(heights)

    def resize(self, size: tuple[int, int]) -> None:
        self._size = size
        width, total_h = size
        heights = layout_flex(self._heights, total_h)

        y = 0
        for child, h in zip(self.children, heights):
            child.x = y + 1
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
            y += h

    def _render_surface(self, surface: "Surface") -> None:
        for child in self.children:
            w, h = child._size
            if w <= 0 or h <= 0:
                continue
            if child.x < 1 or child.y < 1:
                continue
            child._render_surface(
                surface.subsurface(max(0, child.x - 1), max(0, child.y - 1), w, h)
            )

    def accept(self, action: ActionLiteral, **data) -> None:
        """Broadcast action to all children. Skip leaf components that do not
        override ``accept`` (e.g. ``_PickerHeader``).
        """
        for child in self.children:
            if callable(getattr(child, "accept", None)):
                child.accept(action, **data)

    def destroy(self) -> None:
        for child in self.children:
            if callable(getattr(child, "destroy", None)):
                child.destroy()

    def _handle_event(self, key: str) -> None:
        for child in self.children:
            child._handle_event(key)


class Row(Component):
    """Horizontal stack: fixed widths + flex share.

    Children receive geometry from this container; manual ``x, y`` is ignored.
    """

    def __init__(
        self,
        children: Sequence[Component],
        widths: Sequence[Union[int, Literal["flex"]]],
        x: int = 1,
        y: int = 1,
        size: Optional[tuple[int, int]] = None,
    ) -> None:
        super().__init__(x, y, size)
        self.children = list(children)
        for child in self.children:
            child.parent = self
        self._widths = list(widths)

    def set_widths(self, widths: Sequence[Union[int, Literal["flex"]]]) -> None:
        if len(widths) != len(self.children):
            raise ValueError(
                f"widths length mismatch: expected {len(self.children)}, "
                f"got {len(widths)}"
            )
        new_widths = list(widths)
        if new_widths == self._widths:
            return
        self._widths = new_widths

    def resize(self, size: tuple[int, int]) -> None:
        self._size = size
        width, height = size
        widths = layout_flex(self._widths, width)

        x = 0
        for child, w in zip(self.children, widths):
            child.x = 1
            child.y = x + 1
            if w > 0:
                child.resize((w, height))
            _logger.debug(
                "Row resize: child=%s x=%s y=%s size=%s",
                type(child).__name__,
                child.x,
                child.y,
                child._size,
            )
            x += w

    def _render_surface(self, surface: "Surface") -> None:
        for child in self.children:
            w, h = child._size
            if w <= 0 or h <= 0:
                continue
            if child.x < 1 or child.y < 1:
                continue
            child._render_surface(
                surface.subsurface(max(0, child.x - 1), max(0, child.y - 1), w, h)
            )

    def accept(self, action: ActionLiteral, **data) -> None:
        for child in self.children:
            if callable(getattr(child, "accept", None)):
                child.accept(action, **data)

    def destroy(self) -> None:
        for child in self.children:
            if callable(getattr(child, "destroy", None)):
                child.destroy()

    def _handle_event(self, key: str) -> None:
        for child in self.children:
            child._handle_event(key)
