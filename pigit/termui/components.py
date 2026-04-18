# -*- coding: utf-8 -*-
"""
Module: pigit/termui/components.py
Description: Git TUI component tree; drawing uses an injected :class:`~pigit.termui.render.Renderer`.
Author: Zev
Date: 2026-03-27
"""

from __future__ import annotations

import logging
from abc import ABC
from typing import TYPE_CHECKING, Callable, Literal, Optional, Union

from pigit.termui.bindings import (
    BindingsList,
    list_bindings,
    resolve_key_handlers_merged,
)
from pigit.termui.overlay_kinds import OverlayDispatchResult

if TYPE_CHECKING:
    from pigit.termui.layout import LayoutEngine
    from pigit.termui.render import Renderer
    from pigit.termui.surface import Surface

_logger = logging.getLogger(__name__)

NONE_SIZE = (0, 0)

ActionLiteral = Literal["goto"]
KeyRouting = Literal["child_first", "switch_first"]


def _looks_like_overlay_host(candidate: object) -> bool:
    """Duck-type check for a component that owns app-wide overlay session state."""

    return (
        callable(getattr(candidate, "begin_popup_session", None))
        and callable(getattr(candidate, "end_popup_session", None))
    )


class ComponentError(Exception):
    """Error class of ~Component."""


def _render_child_to_surface(
    component: "Component", surface: "Surface", log_prefix: str
) -> None:
    w, h = component._size
    if w <= 0 or h <= 0:
        return
    if component.x < 1 or component.y < 1:
        _logger.warning(
            "%s %s with invalid 1-based coords (%s, %s)",
            log_prefix,
            component.NAME,
            component.x,
            component.y,
        )
    sub = surface.subsurface(
        max(0, component.x - 1), max(0, component.y - 1), w, h
    )
    component._render_surface(sub)


class Component(ABC):
    NAME: str = ""
    BINDINGS: Optional[BindingsList] = None

    def __init__(
        self,
        x: int = 1,
        y: int = 1,
        size: Optional[tuple[int, int]] = None,
        children: Optional[dict[str, "Component"]] = None,
        parent: Optional["Component"] = None,
        renderer: Optional["Renderer"] = None,
    ) -> None:
        assert self.NAME, "The `NAME` attribute cannot be empty."

        self._activated = False  # component whether activated state.

        self.x, self.y = x, y
        self._size = size or NONE_SIZE

        self.parent = parent
        self.children = children
        self._renderer = renderer

        self._key_handlers = resolve_key_handlers_merged(
            self, type(self), self.BINDINGS
        )

    def nearest_overlay_host(self) -> Optional["Component"]:
        """
        Walk parents toward the tree root; return the first ancestor that manages
        overlay sessions (usually :class:`~pigit.termui.root.ComponentRoot`).

        Callers that open modal overlays should use this instead of assuming ``self.parent``
        is the event-loop root (cf. Flutter ``findAncestorStateOfType`` / SwiftUI environment).
        """

        current: Optional["Component"] = self.parent
        while current is not None:
            if _looks_like_overlay_host(current):
                return current
            current = current.parent
        return None

    def activate(self):
        self._activated = True

    def deactivate(self):
        self._activated = False

    def is_activated(self):
        """Get current activate status."""
        return self._activated

    def fresh(self):
        """Fresh content data.

        Here is do nothing. If needed, should overwritten in sub-class.
        """
        raise NotImplementedError()

    def accept(self, action: ActionLiteral, **data):
        """Process emit action of child.

        Here is do nothing. If needed, should overwritten in sub-class.
        """
        raise NotImplementedError()

    def emit(self, action: ActionLiteral, **data):
        """Emit to parent."""
        assert self.parent is not None, "Has no parent to emitting."
        self.parent.accept(action, **data)

    def update(self, action: ActionLiteral, **data):
        """Process notify action of parent.

        Here is do nothing. If needed, should overwritten in sub-class.
        """
        raise NotImplementedError()

    def notify(self, action: ActionLiteral, **data):
        """Notify all children."""
        assert (
            self.children is not None
        ), f"Has no children to notifying; {self.__class__}."
        for child in self.children.values():
            child.update(action, **data)

    def resize(self, size: tuple[int, int]):
        """Response to the resize event.

        Re-set the size of component. And refresh the content.
        If has children, let children process resize.
        """
        self._size = size
        self.fresh()

        # if has no children, None or {}
        if not self.children:
            return

        # let children process resize.
        for child in self.children.values():
            child.resize(size)

    def _render_surface(self, surface: "Surface") -> None:
        """Render this component into the given Surface.

        New components should implement this instead of `_render`.
        """
        pass

    def _handle_event(self, key: str):
        """Event process handle function.

        If want to custom handle, instance function `on_key(str)` in sub-class.
        Or instance attribute `BINDINGS` in sub-class. Support effectiveness both.
        """
        handler = self._key_handlers.get(key)
        if handler is not None:
            handler()

        on_key = getattr(self, "on_key", None)
        if on_key is not None and callable(on_key):
            on_key(key)

    def has_overlay_open(self) -> bool:
        """True when this component is the loop root and an overlay is active."""

        return False

    def try_dispatch_overlay(self, key: str) -> OverlayDispatchResult:
        """
        Handle ``key`` for the active overlay only; must not be used when
        :meth:`has_overlay_open` is false (defensive default).
        """

        return OverlayDispatchResult.DROPPED_UNBOUND

    def get_help_entries(self) -> list[tuple[str, str]]:
        """
        Return ``(key display, description)`` rows for the help panel.

        Default: derived from :func:`~pigit.termui.bindings.list_bindings` (same
        keys as runtime handlers), with short English placeholders when no docstring.
        """

        return _default_help_entries(self)


def _truncate_help_line(text: str, max_len: int = 120) -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - 1] + "\u2026"


def _default_help_entries(component: "Component") -> list[tuple[str, str]]:
    cls = type(component)
    rows: list[tuple[str, str]] = []
    for semantic_key, target in list_bindings(component, cls)[:64]:
        desc = _describe_binding_target(component, target)
        rows.append((semantic_key, _truncate_help_line(desc)))
    return rows


def _describe_binding_target(
    owner: "Component",
    target: Union[str, Callable[..., object]],
) -> str:
    if isinstance(target, str):
        fn = getattr(owner, target, None)
        if callable(fn):
            doc = getattr(fn, "__doc__", None)
            if doc and doc.strip():
                return doc.strip().splitlines()[0].strip()
        return f"{target} action"
    return "bound command"


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
        renderer: Optional["Renderer"] = None,
    ) -> None:
        super().__init__(x, y, size, renderer=renderer)
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
                logging.getLogger().warning(f"Not found child: {name}.")
        else:
            raise ComponentError("Not support action of ~TabView.")

    def _render_surface(self, surface: "Surface") -> None:
        if self._active_child is not None:
            _render_child_to_surface(
                self._active_child, surface, "TabView switch to"
            )

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
        renderer: Optional["Renderer"] = None,
    ) -> None:
        super().__init__(x, y, size, renderer=renderer)
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


class LineTextBrowser(Component):
    def __init__(
        self,
        x: int = 1,
        y: int = 1,
        size: Optional[tuple[int, int]] = None,
        content: Optional[list[str]] = None,
        renderer: Optional["Renderer"] = None,
    ) -> None:
        super().__init__(x, y, size, renderer=renderer)

        self._content = content
        self._max_line = self._size[1]

        self._i = 0  # start display line index of content.

        self._r = [0, self._size[1]]  # display range.

    def resize(self, size: tuple[int, int]):
        self._max_line = size[1]
        super().resize(size)

    def _render_surface(self, surface: "Surface") -> None:
        if self._content is None:
            return
        chunk = self._content[self._i : self._i + self._max_line]
        chunk = chunk[: max(0, self._size[1] - self.x + 1)]
        for idx, line in enumerate(chunk):
            surface.draw_text(idx, 0, line)

    def scroll_up(self, line: int = 1):
        self._i = max(self._i - line, 0)

    def scroll_down(self, line: int = 1):
        self._i = min(self._i + line, max(0, len(self._content) - self._max_line))


class ItemSelector(Component):
    CURSOR: str = "\u2192"
    # Hint for callers: materialize at most this many rows per viewport refresh when building lists.
    PAGE_SIZE: int = 100

    def __init__(
        self,
        x: int = 1,
        y: int = 1,
        size: Optional[tuple[int, int]] = None,
        content: Optional[list[str]] = None,
        renderer: Optional["Renderer"] = None,
    ) -> None:
        super().__init__(x, y, size, renderer=renderer)

        if len(self.CURSOR) > 1:
            raise ComponentError("error")

        self.content = content or [""]
        self.content_len = len(self.content) - 1

        self.curr_no = 0  # default start with 0.
        self._r_start = 0

    @property
    def visible_row_count(self) -> int:
        """Viewport height in rows (how many list lines are painted per frame)."""
        return self._size[1]

    @property
    def visible_items(self):
        """Content rows in the current scroll window (pagination / virtual window)."""
        return self.content[self._r_start : self._r_start + self.visible_row_count]

    def set_content(self, content: list[str]):
        self.content = content
        self.content_len = len(self.content) - 1

    def clear_items(self):
        self.set_content([""])

    def update(self, action: ActionLiteral, **data):
        pass

    def _render_surface(self, surface: "Surface") -> None:
        if not self.content:
            return
        visible = self.visible_items[: max(0, self._size[1] - self.x + 1)]
        for idx, item in enumerate(visible):
            no = self._r_start + idx
            prefix = self.CURSOR if no == self.curr_no else " "
            surface.draw_text(idx, 0, f"{prefix}{item}")

    def next(self, step: int = 1):
        tmp_no = self.curr_no + step
        if tmp_no < 0 or tmp_no > self.content_len:
            return

        self.curr_no += step
        if self.curr_no >= self._r_start + self._size[1]:
            self._r_start += step

    def forward(self, step: int = 1):
        tmp = self.curr_no - step
        if tmp < 0 or tmp > self.content_len:
            return

        self.curr_no -= step
        if self.curr_no < self._r_start:
            self._r_start -= step


class GitPanelLazyResizeMixin:
    """Defer expensive :meth:`fresh` until the panel is activated.

    Inactive panels show a one-line placeholder until first shown, so startup
    ``resize`` avoids running git for every tab. Pair with a container that
    calls :meth:`fresh` when switching to the active child (:meth:`TabView.switch_child`).
    """

    _panel_loaded: bool = False

    def resize(self, size: tuple[int, int]) -> None:
        self._size = size
        if self.is_activated():
            self.fresh()
            self._panel_loaded = True
        elif not self._panel_loaded:
            self.set_content(["Loading..."])
            self.curr_no = 0
            self._r_start = 0
