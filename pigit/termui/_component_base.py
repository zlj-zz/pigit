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
from typing import TYPE_CHECKING, Callable, Optional, Sequence, Union

from ._bindings import (
    BindingsList,
    list_bindings,
    resolve_key_handlers_merged,
)
from ._renderer_context import (
    get_renderer,
    get_renderer_strict,
)
from .types import ActionEventType, OverlayDispatchResult

if TYPE_CHECKING:
    from ._renderer import Renderer
    from ._surface import Surface

_logger = logging.getLogger(__name__)

NONE_SIZE = (0, 0)


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
            type(component).__name__,
            component.x,
            component.y,
        )
    sub = surface.subsurface(max(0, component.x - 1), max(0, component.y - 1), w, h)
    component._render_surface(sub)


class Component(ABC):
    """Base class for all TUI components.

    Provides the component tree (parent/children), size/position,
    key-handler resolution, action dispatch, and lifecycle hooks.
    Subclasses must implement :meth:`_render_surface`.
    """

    BINDINGS: Optional[BindingsList] = None

    def __init__(
        self,
        x: int = 1,
        y: int = 1,
        size: Optional[tuple[int, int]] = None,
        children: Optional[Sequence["Component"]] = None,
        parent: Optional["Component"] = None,
    ) -> None:
        self._activated = False

        self.x, self.y = x, y
        self._size = size or NONE_SIZE

        self.parent = parent
        self.children = list(children) if children else []

        self._key_handlers = resolve_key_handlers_merged(
            self, type(self), self.BINDINGS
        )

    def activate(self):
        """Mark the component as active. Called when it enters the visible tree."""
        self._activated = True

    def deactivate(self):
        """Mark the component as inactive. Called when it leaves the visible tree."""
        self._activated = False

    def is_activated(self):
        """Get current activate status."""
        return self._activated

    def refresh(self):
        """Fresh content data.

        Default is no-op; override if the component needs to rebuild internal
        state when resized or notified.
        """
        pass

    def accept(self, action: ActionEventType, **data):
        """Process emit action of child."""
        _logger.warning(
            "%s.accept: unsupported action %r",
            type(self).__name__,
            action,
        )

    def emit(self, action: ActionEventType, **data):
        """Emit to parent."""
        if self.parent is None:
            raise ComponentError("Has no parent to emitting.")
        self.parent.accept(action, **data)

    def update(self, action: ActionEventType, **data):
        """Process notify action of parent."""
        _logger.warning(
            "%s.update: unsupported action %r",
            type(self).__name__,
            action,
        )

    def notify(self, action: ActionEventType, **data):
        """Notify all children."""
        for child in self.children:
            child.update(action, **data)

    def resize(self, size: tuple[int, int]) -> None:
        """Response to the resize event.

        Subclasses that manage child geometry (e.g. Column, Row, TabView)
        must override this method to propagate the correct size to each child.
        """
        self._size = size
        self.refresh()

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

    def get_help_title(self) -> str:
        """Return the title for this component's help section.

        Default is the class name without "Component" suffix, if present.
        """
        name = type(self).__name__
        if name.endswith("Component"):
            return name[: -len("Component")]
        return name

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
