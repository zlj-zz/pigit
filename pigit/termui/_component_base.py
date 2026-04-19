# -*- coding: utf-8 -*-
"""
Module: pigit/termui/_component_base.py
Description: Base Component class and related utilities for the TUI framework.
Author: Zev
Date: 2026-04-19
"""

from __future__ import annotations

import logging
from abc import ABC
from typing import TYPE_CHECKING, Callable, Optional, Union

from ._bindings import (
    BindingsList,
    list_bindings,
    resolve_key_handlers_merged,
)
from ._renderer_context import (
    get_renderer,
    get_renderer_strict,
)
from .types import ActionLiteral, OverlayDispatchResult

if TYPE_CHECKING:
    from ._layout import LayoutEngine
    from ._renderer import Renderer
    from ._surface import Surface

_logger = logging.getLogger(__name__)

NONE_SIZE = (0, 0)


def _looks_like_overlay_host(candidate: object) -> bool:
    """Duck-type check for a component that owns app-wide overlay session state."""

    return callable(getattr(candidate, "begin_popup_session", None)) and callable(
        getattr(candidate, "end_popup_session", None)
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
    sub = surface.subsurface(max(0, component.x - 1), max(0, component.y - 1), w, h)
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
    ) -> None:
        assert self.NAME, "The `NAME` attribute cannot be empty."

        self._activated = False  # component whether activated state.

        self.x, self.y = x, y
        self._size = size or NONE_SIZE

        self.parent = parent
        self.children = children

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

    @property
    def renderer(self) -> Optional["Renderer"]:
        """Get the current renderer from context.

        Returns:
            The current Renderer instance, or None if not in event loop.
        """
        return get_renderer()

    @property
    def renderer_strict(self) -> "Renderer":
        """Get renderer, raising if not available.

        Returns:
            The current Renderer instance.

        Raises:
            RendererNotBoundError: If not within AppEventLoop context.
        """
        return get_renderer_strict()


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
