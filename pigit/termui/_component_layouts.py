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
        self._children = list(children)
        for child in self._children:
            if child.parent is not None and child.parent is not self:
                _logger.warning("Reparenting %s to TabView", type(child).__name__)
            child.parent = self

        self._shortcuts = dict(shortcuts) if shortcuts else {}
        for key, panel in self._shortcuts.items():
            if panel not in self._children:
                raise ComponentError(
                    f"shortcuts['{key}'] -> {type(panel).__name__} not in children"
                )

        if not self._children:
            raise ComponentError("children cannot be empty.")
        if start is None:
            start = self._children[0]
        if start not in self._children:
            raise ComponentError(
                f"start {type(start).__name__} not in children. "
                f"Available: {[type(c).__name__ for c in self._children]}."
            )
        self._active = start
        self._active.activate()

    @property
    def active(self) -> Optional[Component]:
        """Return the currently active child panel."""
        return self._active

    def route_to(self, target: Component) -> Optional[Component]:
        """Switch to the given child component."""
        if target not in self._children:
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
            if isinstance(target, Component) and target in self._children:
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
        for child in self._children:
            child.resize(size)

    def notify(self, action: ActionLiteral, **data) -> None:
        for child in self._children:
            child.update(action, **data)

    def _render_surface(self, surface: "Surface") -> None:
        if self._active is not None:
            _render_child_to_surface(self._active, surface, "TabView")

    def _handle_event(self, key: str):
        if self._shortcuts:
            panel = self._shortcuts.get(key)
            if panel is not None and panel in self._children:
                if panel is not self._active:
                    self.route_to(panel)
                    return
        if self._active is not None:
            self._active._handle_event(key)


class Column(Component):
    """Vertical stack: fixed heights + flex share.

    Children receive geometry from this container; manual ``x, y`` is ignored.
    This component does **not** set ``self.children`` — it uses ``_child_list``
    to maintain ordering and overrides all methods that would otherwise iterate
    over ``self.children`` (``resize``, ``notify``, ``accept``, ``fresh``).
    """

    def __init__(
        self,
        children: Sequence[Component],
        heights: Sequence[Union[int, Literal["flex"]]],
        x: int = 1,
        y: int = 1,
        size: Optional[tuple[int, int]] = None,
    ) -> None:
        super().__init__(x, y, size, children=None)
        self._child_list = list(children)
        for child in self._child_list:
            child.parent = self
        self._heights = list(heights)

    def set_heights(self, heights: Sequence[Union[int, Literal["flex"]]]) -> None:
        if len(heights) != len(self._child_list):
            raise ValueError(
                f"heights length mismatch: expected {len(self._child_list)}, "
                f"got {len(heights)}"
            )
        self._heights = list(heights)

    def resize(self, size: tuple[int, int]) -> None:
        self._size = size
        width, total_h = size
        ox, oy = self.x - 1, self.y - 1

        fixed = sum(h for h in self._heights if h != "flex")
        flex_n = sum(1 for h in self._heights if h == "flex")
        if total_h < fixed:
            flex_h = 0
        else:
            flex_h = max(0, total_h - fixed) // flex_n if flex_n else 0

        # First pass: compute all geometries
        y = oy
        flex_items: list[tuple[int, int]] = []
        geometries: list[tuple[int, int, int, int]] = []
        for i, (child, h) in enumerate(zip(self._child_list, self._heights)):
            if h == "flex":
                flex_items.append((i, flex_h))
                h_val = flex_h
            else:
                remaining = max(0, total_h - (y - oy))
                h_val = min(h, remaining)
            geometries.append((y + 1, oy + 1, width, h_val))
            y += h_val

        # Remainder pixels go to the last flex child (no truncation loss)
        if flex_items and total_h >= fixed:
            remainder = total_h - fixed - flex_h * flex_n
            if remainder > 0:
                last_idx, last_h = flex_items[-1]
                gx, gy, gw, _ = geometries[last_idx]
                geometries[last_idx] = (gx, gy, gw, last_h + remainder)

        # Second pass: apply via child.resize() so subclasses handle their own _size
        for child, (cx, cy, cw, ch) in zip(self._child_list, geometries):
            child.x = cx
            child.y = cy
            if ch > 0:
                child.resize((cw, ch))

    def _render_surface(self, surface: "Surface") -> None:
        for child in self._child_list:
            w, h = child._size
            if w <= 0 or h <= 0:
                continue
            if child.x < 1 or child.y < 1:
                continue
            child._render_surface(
                surface.subsurface(max(0, child.x - 1), max(0, child.y - 1), w, h)
            )

    def notify(self, action: ActionLiteral, **data) -> None:
        for child in self._child_list:
            child.update(action, **data)

    def accept(self, action: ActionLiteral, **data) -> None:
        """Broadcast action to all children. Skip leaf components that do not
        override ``accept`` (e.g. ``_PickerHeader``).
        """
        for child in self._child_list:
            if callable(getattr(child, "accept", None)):
                child.accept(action, **data)

    def destroy(self) -> None:
        for child in self._child_list:
            if callable(getattr(child, "destroy", None)):
                child.destroy()

    def fresh(self) -> None:
        pass

    def _handle_event(self, key: str) -> None:
        for child in self._child_list:
            child._handle_event(key)


class Row(Component):
    """Horizontal stack: fixed widths + flex share.

    Children receive geometry from this container; manual ``x, y`` is ignored.
    This component uses ``_child_list`` to maintain ordering.
    """

    def __init__(
        self,
        children: Sequence[Component],
        widths: Sequence[Union[int, Literal["flex"]]],
        x: int = 1,
        y: int = 1,
        size: Optional[tuple[int, int]] = None,
    ) -> None:
        super().__init__(x, y, size, children=None)
        self._child_list = list(children)
        for child in self._child_list:
            child.parent = self
        self._widths = list(widths)

    def set_widths(
        self, widths: Sequence[Union[int, Literal["flex"]]]
    ) -> None:
        if len(widths) != len(self._child_list):
            raise ValueError(
                f"widths length mismatch: expected {len(self._child_list)}, "
                f"got {len(widths)}"
            )
        new_widths = list(widths)
        if new_widths == self._widths:
            return
        self._widths = new_widths

    def resize(self, size: tuple[int, int]) -> None:
        self._size = size
        width, height = size
        ox, oy = self.x - 1, self.y - 1

        fixed = sum(w for w in self._widths if w != "flex")
        flex_n = sum(1 for w in self._widths if w == "flex")
        if width < fixed:
            flex_w = 0
        else:
            flex_w = max(0, width - fixed) // flex_n if flex_n else 0

        x = 0
        flex_items: list[tuple[int, int]] = []
        geometries: list[tuple[int, int, int, int]] = []
        for i, (child, w) in enumerate(zip(self._child_list, self._widths)):
            if w == "flex":
                flex_items.append((i, flex_w))
                w_val = flex_w
            else:
                remaining = max(0, width - x)
                w_val = min(w, remaining)
            geometries.append((1, x + 1, w_val, height))
            x += w_val

        if flex_items and width >= fixed:
            remainder = width - fixed - flex_w * flex_n
            if remainder > 0:
                last_idx, last_w = flex_items[-1]
                gx, gy, _, gh = geometries[last_idx]
                geometries[last_idx] = (gx, gy, last_w + remainder, gh)

        for child, (cx, cy, cw, ch) in zip(self._child_list, geometries):
            child.x = cx
            child.y = cy
            if cw > 0:
                child.resize((cw, ch))

    def _render_surface(self, surface: "Surface") -> None:
        for child in self._child_list:
            w, h = child._size
            if w <= 0 or h <= 0:
                continue
            if child.x < 1 or child.y < 1:
                continue
            child._render_surface(
                surface.subsurface(max(0, child.x - 1), max(0, child.y - 1), w, h)
            )

    def notify(self, action: ActionLiteral, **data) -> None:
        for child in self._child_list:
            child.update(action, **data)

    def accept(self, action: ActionLiteral, **data) -> None:
        for child in self._child_list:
            if callable(getattr(child, "accept", None)):
                child.accept(action, **data)

    def destroy(self) -> None:
        for child in self._child_list:
            if callable(getattr(child, "destroy", None)):
                child.destroy()

    def fresh(self) -> None:
        pass

    def _handle_event(self, key: str) -> None:
        for child in self._child_list:
            child._handle_event(key)
