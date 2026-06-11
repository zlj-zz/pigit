"""
Module: pigit/termui/_runtime_context.py
Description: Unified RuntimeContext for termui — all runtime state in a single
    ContextVar-managed object.  No other context module should define
    duplicate ContextVars.
Author: Zev
Date: 2026-05-17
"""

from __future__ import annotations

import contextvars
import logging
from typing import TYPE_CHECKING, TypeVar, cast
from collections.abc import Callable

from ._layer import LayerKind

if TYPE_CHECKING:
    from ._component import Component
    from ._renderer import Renderer
    from ._root import ComponentRoot
    from ._session import Session

_logger = logging.getLogger(__name__)

T = TypeVar("T", bound="Component")

__all__ = [
    "RuntimeContext",
    "ComponentRegistry",
    "FocusManager",
    "RendererNotBoundError",
    "set_session",
    "reset_session",
    "get_session",
    "set_renderer",
    "reset_renderer",
    "get_renderer",
    "get_renderer_strict",
    "set_overlay_host",
    "reset_overlay_host",
    "get_overlay_host",
    "layer_push",
    "layer_pop",
    "layer_top",
    "is_modal_open",
    "get_registry",
    "set_registry",
    "reset_registry",
    "by_id",
    "set_focus_manager",
    "reset_focus_manager",
    "get_focus_manager",
    "set_render_request",
    "reset_render_request",
    "get_render_request",
    "request_render",
]

# Single ContextVar holding the unified runtime state.
_runtime_ctx: contextvars.ContextVar[RuntimeContext | None] = contextvars.ContextVar(
    "runtime", default=None
)


# --- RendererNotBoundError ---


class RendererNotBoundError(RuntimeError):
    """Raised when attempting to access renderer before context is set."""

    def __init__(self) -> None:
        super().__init__(
            "Renderer not bound to current context. "
            "Ensure component is rendered within AppEventLoop.run()"
        )


# --- ComponentRegistry ---


class ComponentRegistry:
    """Id-based component registry for O(1) lookup within a component tree."""

    def __init__(self) -> None:
        self._by_id: dict[str, Component] = {}

    def register(self, component: Component) -> None:
        if not component.id:
            return
        if component.id in self._by_id:
            _logger.warning(
                "Duplicate component id %r: %s overwrites %s",
                component.id,
                type(component).__name__,
                type(self._by_id[component.id]).__name__,
            )
        self._by_id[component.id] = component

    def unregister(self, component: Component) -> None:
        if component.id:
            self._by_id.pop(component.id, None)

    def by_id(self, id: str) -> Component | None:
        return self._by_id.get(id)


# --- FocusManager ---


class FocusManager:
    """Manages the focus chain within a component tree.

    Replaces the module-level ``_set_focus_chain`` global function and
    ``_last_focused`` variable.  A single ``FocusManager`` instance is
    bound to a ``RuntimeContext`` and tracks which leaf component currently
    holds focus by updating ``_focus_level`` along the parent chain.
    """

    _MAX_FOCUS_STACK = 8

    def __init__(self, root: ComponentRoot) -> None:
        self._root = root
        self._leaf: Component | None = None
        self._focus_stack: list[Component | None] = []

    # --- Policy API (high-level decisions about where focus should go) ---

    def _resolve_overlay_target(self, overlay: Component) -> Component:
        """Walk the presented_child chain to the deepest leaf."""
        from ._component import resolve_presented

        result = resolve_presented(overlay)
        return result if result is not None else overlay

    def sync_focus_to_overlay_or_leaf(self) -> None:
        """Set focus to the top open overlay, or body leaf if none."""
        top = self._root._top_open_overlay()
        if top is not None:
            self.set_focus_chain(self._resolve_overlay_target(top))
        else:
            self.set_focus_chain(self._root.body.find_focus_leaf())

    def sync_focus_to_overlay(self) -> None:
        """If an overlay is open, set focus to its deepest presented child."""
        top = self._root._top_open_overlay()
        if top is not None:
            self.set_focus_chain(self._resolve_overlay_target(top))

    def sync_focus_if_overlay_closed(self, was_open: bool, now_open: bool) -> None:
        """Restore focus to body leaf when an overlay closes."""
        if was_open and not now_open:
            self.set_focus_chain(self._root.body.find_focus_leaf())

    def get_event_target(self) -> Component | None:
        """Return the component that should receive the next key event."""
        leaf = self._leaf or self._root.body.find_focus_leaf()
        if leaf is None:
            return None
        node: Component | None = leaf
        for _ in range(128):
            if node is None:
                break
            parent = node.parent
            if (
                parent is not None
                and parent.presented_child is node
                and parent.event_target is node
            ):
                return parent
            node = parent
        return leaf

    # --- Mechanics API (low-level focus chain manipulation) ---

    def focus_grab(self, component: Component) -> None:
        """Temporarily shift focus to *component*, saving the current leaf.

        Use :meth:`focus_release` to restore the previous focus chain.
        """
        if len(self._focus_stack) >= self._MAX_FOCUS_STACK:
            _logger.warning("Focus stack overflow; dropping oldest entry")
            self._focus_stack.pop(0)
        self._focus_stack.append(self._leaf)
        self.set_focus_chain(component)

    def focus_release(self) -> None:
        """Restore focus to the leaf saved by the most recent :meth:`focus_grab`."""
        if not self._focus_stack:
            return
        prev = self._focus_stack.pop()
        if prev is not None:
            self.set_focus_chain(prev)
        else:
            self.clear_focus()

    def set_focus_chain(self, leaf: Component) -> None:
        """Set ``_focus_level`` along the parent chain from *leaf* to root.

        The leaf receives level ``0``, its parent ``1``, and so on.
        All previously-focused nodes are reset to ``-1``.
        """
        if self._leaf is leaf:
            return
        old = self._leaf
        for _ in range(128):
            if old is None:
                break
            old._focus_level = -1
            old = old.parent
        level = 0
        node: Component | None = leaf
        for _ in range(128):
            if node is None:
                break
            node._focus_level = level
            level += 1
            node = node.parent
        self._leaf = leaf

    def get_focus_leaf(self) -> Component | None:
        """Return the component that currently holds focus, or ``None``."""
        return self._leaf

    def clear_focus(self) -> None:
        """Reset the focus chain and clear the stored leaf."""
        old = self._leaf
        while old is not None:
            old._focus_level = -1
            old = old.parent
        self._leaf = None


# --- RuntimeContext ---


class RuntimeContext:
    """Unified runtime state container for a single TUI session.

    Holds references to all runtime-scoped subsystems. Access the active
    instance via :meth:`RuntimeContext.current`.

    This is a **mutable** container — fields are updated in-place by
    ``set_*`` helpers rather than pushing/popping multiple ContextVars.
    """

    def __init__(self) -> None:
        self.session: Session | None = None
        self.renderer: Renderer | None = None
        self.overlay_host: ComponentRoot | None = None
        self.registry: ComponentRegistry | None = ComponentRegistry()
        self.focus_manager: FocusManager | None = None
        self.render_request: Callable[[], None] | None = None

    @classmethod
    def current(cls) -> RuntimeContext | None:
        """Return the active RuntimeContext, or ``None`` if not set."""
        return _runtime_ctx.get()


# --- Session context helpers ---


def set_session(session: Session) -> None:
    """Set the current TUI session in context."""
    runtime = _runtime_ctx.get()
    if runtime is not None:
        runtime.session = session


def reset_session(token: object | None = None) -> None:
    """Reset session context to ``None``.

    Args:
        token: Ignored; kept for backward compatibility with old code
            that passed a ContextVar token.
    """
    runtime = _runtime_ctx.get()
    if runtime is not None:
        runtime.session = None


def get_session() -> Session | None:
    """Get the current TUI session from context."""
    runtime = _runtime_ctx.get()
    return runtime.session if runtime is not None else None


# --- Renderer context helpers ---


def set_renderer(renderer: Renderer) -> None:
    """Set renderer in current context."""
    runtime = _runtime_ctx.get()
    if runtime is not None:
        runtime.renderer = renderer


def reset_renderer(token: object | None = None) -> None:
    """Reset renderer context to ``None``.

    Args:
        token: Ignored; kept for backward compatibility.
    """
    runtime = _runtime_ctx.get()
    if runtime is not None:
        runtime.renderer = None


def get_renderer() -> Renderer | None:
    """Get the current renderer from context."""
    runtime = _runtime_ctx.get()
    return runtime.renderer if runtime is not None else None


def get_renderer_strict() -> Renderer:
    """Get the current renderer, raising if not set."""
    renderer = get_renderer()
    if renderer is None:
        raise RendererNotBoundError()
    return renderer


# --- Overlay host context helpers ---


def set_overlay_host(host: ComponentRoot) -> None:
    """Set the current overlay host in context."""
    runtime = _runtime_ctx.get()
    if runtime is not None:
        runtime.overlay_host = host


def reset_overlay_host(token: object | None = None) -> None:
    """Reset overlay host context to ``None``.

    Args:
        token: Ignored; kept for backward compatibility.
    """
    runtime = _runtime_ctx.get()
    if runtime is not None:
        runtime.overlay_host = None


def get_overlay_host() -> ComponentRoot | None:
    """Return the current overlay host, or ``None`` if not inside a TUI session."""
    runtime = _runtime_ctx.get()
    return runtime.overlay_host if runtime is not None else None


# --- Layer stack helpers ---


def layer_push(kind: LayerKind, overlay: Component) -> None:
    """Push an overlay onto the specified layer."""
    host = get_overlay_host()
    if host is not None:
        host._layer_stack.push(kind, overlay)


def layer_pop(kind: LayerKind) -> Component | None:
    """Pop the top component from the specified layer."""
    host = get_overlay_host()
    if host is not None:
        return host._layer_stack.pop(kind)
    return None


def layer_top(kind: LayerKind) -> Component | None:
    """Return the top component on the specified layer, or ``None``."""
    host = get_overlay_host()
    if host is not None:
        return host._layer_stack.top(kind)
    return None


def is_modal_open() -> bool:
    """Return ``True`` if a modal popup is currently open."""
    return layer_top(LayerKind.MODAL) is not None


# --- Registry context helpers ---


def get_registry() -> ComponentRegistry | None:
    """Get current registry from context."""
    runtime = _runtime_ctx.get()
    return runtime.registry if runtime is not None else None


def set_registry(registry: ComponentRegistry) -> None:
    """Set the current component registry in context."""
    runtime = _runtime_ctx.get()
    if runtime is not None:
        runtime.registry = registry


def reset_registry(token: object | None = None) -> None:
    """Reset registry context to ``None``.

    Args:
        token: Ignored; kept for backward compatibility.
    """
    runtime = _runtime_ctx.get()
    if runtime is not None:
        runtime.registry = None


def by_id(id: str, expect_type: type[T] | None = None) -> T:
    """Find component by its unique identifier in the current registry context.

    Args:
        id: Component identifier.
        expect_type: Optional expected component type. If the found component
            is not an instance of this type, raises TypeError.

    Returns:
        The component instance.

    Raises:
        RuntimeError: If no component with the given id is found.
        TypeError: If expect_type is given and the found component mismatches.
    """
    reg = get_registry()
    comp = reg.by_id(id) if reg else None
    if comp is None:
        raise RuntimeError(f"Component {id!r} not found")
    if expect_type is not None and not isinstance(comp, expect_type):
        raise TypeError(
            f"Component {id!r} is {type(comp).__name__}, expected {expect_type.__name__}"
        )
    return cast(T, comp)


# --- FocusManager context helpers ---


def set_focus_manager(fm: FocusManager) -> None:
    """Set the current FocusManager in context."""
    runtime = _runtime_ctx.get()
    if runtime is not None:
        runtime.focus_manager = fm


def reset_focus_manager(token: object | None = None) -> None:
    """Reset FocusManager context to ``None``.

    Args:
        token: Ignored; kept for backward compatibility.
    """
    runtime = _runtime_ctx.get()
    if runtime is not None:
        runtime.focus_manager = None


def get_focus_manager() -> FocusManager | None:
    """Get the current FocusManager from context."""
    runtime = _runtime_ctx.get()
    return runtime.focus_manager if runtime is not None else None


# --- Render request context helpers ---


def set_render_request(callback: Callable[[], None]) -> None:
    """Set the current render request callback in context."""
    runtime = _runtime_ctx.get()
    if runtime is not None:
        runtime.render_request = callback


def reset_render_request(token: object | None = None) -> None:
    """Reset render request context to ``None``.

    Args:
        token: Ignored; kept for backward compatibility.
    """
    runtime = _runtime_ctx.get()
    if runtime is not None:
        runtime.render_request = None


def get_render_request() -> Callable[[], None] | None:
    """Get the current render request callback from context."""
    runtime = _runtime_ctx.get()
    return runtime.render_request if runtime is not None else None


def request_render() -> None:
    """Request a render of the component tree.

    The actual coalescing happens at the event-loop level (e.g.
    ``AppEventLoop.request_render`` sets a flag that is cleared once per
    frame). This function simply forwards the request to the callback
    registered in the current runtime context.

    Safe to call from Signal subscribers or any component callback.
    """
    cb = get_render_request()
    _logger.debug("[RENDER] request_render cb=%s", cb is not None)
    if cb is not None:
        cb()
