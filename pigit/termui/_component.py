"""
Module: pigit/termui/_component.py
Description: Base Component class and related utilities for the TUI framework.
Author: Zev
Date: 2026-04-19
"""

from __future__ import annotations

import logging
from abc import ABC
from dataclasses import dataclass
from typing import Any, TYPE_CHECKING
from collections.abc import Callable, Sequence

from ._bindings import (
    BindingsList,
    derive_help_entries,
    resolve_action_keys,
    resolve_instance_bindings,
)
from ._mouse import MouseEvent
from .keys import display_key
from ._runtime_context import (
    get_renderer,
    get_renderer_strict,
)
from .reactive import Computed, Signal
from .types import EventType, OverlayDispatchResult

if TYPE_CHECKING:
    from ._renderer import Renderer
    from ._surface import Surface, _Subsurface

_logger = logging.getLogger(__name__)

NONE_SIZE = (0, 0)


@dataclass(eq=False)
class _Subscription:
    """Internal record tracking a framework-level event subscription."""

    action: EventType
    handler: Callable[..., bool | None]
    pending: bool = True
    unsub: Callable[[], None] | None = None

    def cancel(self) -> None:
        if self.unsub is not None:
            self.unsub()


class ComponentError(Exception):
    """Error class of ~Component."""


def render_child(
    component: Component,
    surface: Surface,
    log_prefix: str = "",
) -> None:
    """Blit ``component`` into ``surface`` using the child's x/y/_size (1-based).

    Args:
        component: Child component to render into ``surface``.
        surface: Target draw surface (1-based child coords are converted internally).
        log_prefix: Prefix for invalid-coordinate warning logs.
    """
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


def _render_child_to_surface(
    component: Component, surface: Surface | _Subsurface, log_prefix: str
) -> None:
    render_child(component, surface, log_prefix)


class Component(ABC):
    """Base class for all TUI components.

    Skeleton class containing tree structure, geometry, rendering,
    key handling, event bubbling, and lifecycle hooks.
    Subclasses must implement :meth:`_render_surface`.
    """

    BINDINGS: BindingsList | None = None
    tab_name: str = ""
    tab_key: str = ""

    def __init__(
        self,
        x: int = 1,
        y: int = 1,
        size: tuple[int, int] | None = None,
        children: Sequence[Component] | None = None,
        parent: Component | None = None,
        id: str | None = None,
    ) -> None:
        self._activated = False
        self._focus_level: int = -1

        self.x, self.y = x, y
        self._size = size or NONE_SIZE

        self.parent = parent
        self.children = list(children) if children else []

        self.id = id
        self._try_register_id()

        self._action_bindings, self._key_handlers = resolve_instance_bindings(self)
        self._subscriptions: list[_Subscription] = []

    def activate(self):
        """Mark the component as active. Called when it enters the visible tree."""
        self._unsubscribe_all()
        self._replay_pending_subscriptions()
        self._activated = True

    def deactivate(self):
        """Mark the component as inactive. Called when it leaves the visible tree."""
        self._unsubscribe_all()
        self._activated = False

    def is_activated(self):
        """Get current activate status."""
        return self._activated

    def subscribe(
        self,
        action: EventType,
        handler: Callable[..., bool | None],
    ) -> Callable[[], None]:
        """Subscribe to a framework-level event.

        If the component is not yet mounted, the subscription is queued and
        replayed on activation. The returned callback unsubscribes the handler.
        """
        from ._root import ComponentRoot

        root = self._root_component()
        bus = root.event_bus if isinstance(root, ComponentRoot) else None
        sub = _Subscription(action=action, handler=handler)
        self._subscriptions.append(sub)

        if bus is not None:
            sub.pending = False
            sub.unsub = bus.subscribe(action, handler)
        else:
            sub.pending = True

        def delayed_unsub() -> None:
            if sub.pending:
                try:
                    self._subscriptions.remove(sub)
                except ValueError:
                    pass
                return
            sub.cancel()
            try:
                self._subscriptions.remove(sub)
            except ValueError:
                pass

        return delayed_unsub

    def _replay_pending_subscriptions(self) -> None:
        from ._root import ComponentRoot

        root = self._root_component()
        bus = root.event_bus if isinstance(root, ComponentRoot) else None
        if bus is None:
            return
        for sub in self._subscriptions:
            if sub.pending:
                sub.pending = False
                sub.unsub = bus.subscribe(sub.action, sub.handler)

    def _unsubscribe_all(self) -> None:
        """Cancel active subscriptions and remove them from the list."""
        for sub in list(self._subscriptions):
            if not sub.pending:
                sub.cancel()
                self._subscriptions.remove(sub)

    def _root_component(self) -> Any:
        """Walk parent chain to find the ComponentRoot, if mounted."""
        from ._root import ComponentRoot

        node = self.parent
        while node is not None:
            if isinstance(node, ComponentRoot):
                return node
            node = node.parent
        return None

    def _try_register_id(self) -> None:
        """Register with the global component registry if an id is set."""
        if not self.id:
            return
        from ._runtime_context import get_registry

        reg = get_registry()
        if reg is not None:
            reg.register(self)

    def _try_unregister_id(self) -> None:
        """Unregister from the global component registry if an id is set."""
        if not self.id:
            return
        from ._runtime_context import get_registry

        reg = get_registry()
        if reg is not None:
            reg.unregister(self)

    def destroy(self) -> None:
        """Destroy children and unregister from component registry."""
        self.deactivate()
        for child in self.children:
            child.destroy()
        self._try_unregister_id()

    def hide(self) -> None:
        """Close or hide this component. No-op by default; overlays override."""

    @property
    def size(self) -> tuple[int, int]:
        """Current (width, height) assigned by the last resize()."""
        return self._size

    def refresh(self):
        """Fresh content data.

        Default is no-op; override if the component needs to rebuild internal
        state when resized or notified.
        """

    def resize(self, size: tuple[int, int]) -> None:
        """Response to the resize event.

        Subclasses that manage child geometry (e.g. Column, Row, TabView)
        must override this method to propagate the correct size to each child.
        """
        self._size = size
        self.refresh()

    def capture_key(self, key: str) -> bool:
        """Return True to consume the key before any binding.

        Override for modal input (e.g. an active text filter) that must
        intercept keys ahead of the component's key bindings.
        """
        return False

    def _handle_event(self, key: str) -> bool:
        """Process a key event. Delegates to the event dispatch algorithm."""
        from ._component_event import dispatch_key

        return dispatch_key(self, key)

    def handle_mouse(self, event: MouseEvent) -> bool:
        """Handle a mouse event at this component's local coordinates.

        Returns True when consumed. The default is False (not interactive);
        interactive components override this to map a click/wheel to an action.
        """
        return False

    def _handle_mouse(self, event: MouseEvent) -> bool:
        """Route a mouse event to this component (default: interpret directly).

        ``ComponentRoot`` overrides this to hit-test the tree and route to the
        component under the cursor; leaves interpret the event via
        :meth:`handle_mouse`.
        """
        return self.handle_mouse(event)

    def _hit_test(self, col: int, row: int) -> tuple[Component, int, int] | None:
        """Return the deepest component under 1-based ``(col, row)``.

        The result is ``(component, local_col, local_row)`` where the local
        coordinates are 1-based relative to the returned component. Mirrors
        rendering: children painted last are tested first, and a child's
        ``x``/``y`` (1-based, parent-relative) offset the recursion.
        """
        for child in reversed(self.children):
            w, h = child._size
            if w <= 0 or h <= 0:
                continue
            if not (child.y <= col < child.y + w and child.x <= row < child.x + h):
                continue
            hit = child._hit_test(col - (child.y - 1), row - (child.x - 1))
            if hit is not None:
                return hit
        return self, col, row

    def emit(self, action: EventType, **data) -> None:
        """Bubble action up through parent chain to Application.

        Stops at the first ancestor whose ``on_event`` returns True.
        If no handler consumes it, logs a warning.
        """
        from ._component_event import bubble_event

        bubble_event(self, action, **data)

    def notify(self, action: EventType, **data) -> None:
        """Notify all children by calling their ``update`` method."""
        from ._component_event import notify_children

        notify_children(self, action, **data)

    def _render_surface(self, surface: Surface | _Subsurface) -> None:
        """Render this component into the given Surface.

        New components should implement this instead of `_render`.
        """

    def has_overlay_open(self) -> bool:
        """Return True if an overlay is open. Base components never have overlays."""
        return False

    def try_dispatch_overlay(self, key: str) -> OverlayDispatchResult:
        """Dispatch a key to an overlay. Base components have no overlays."""
        return OverlayDispatchResult.DROPPED_UNBOUND

    def accept(self, action: EventType, **data) -> None:
        """Handle an action event broadcast from a parent container.

        Default is no-op; container components override this to route or
        broadcast to children.
        """

    def update(self, action: EventType, **data) -> None:
        """Receive an action update from a parent or sibling component.

        Default is no-op; interactive components override this to react to
        state changes (e.g. a panel refreshing when another panel changes).
        """

    @property
    def focus_child(self) -> Component | None:
        """Child that currently holds focus among this node's children.

        ``None`` means this node does not manage focus (not "I am the leaf").
        """
        return None

    @property
    def presentation_child(self) -> Component | None:
        """Chrome delegate. ``None`` means this node is the presentation unit."""
        return None

    @property
    def is_focus_leaf(self) -> bool:
        """Return True if this component is the resolved focus leaf."""
        return self._focus_level == 0

    @property
    def renderer(self) -> Renderer | None:
        """Get the current renderer from context.

        Returns:
            The current Renderer instance, or None if not in event loop.
        """
        return get_renderer()

    @property
    def renderer_strict(self) -> Renderer:
        """Get renderer, raising if not available.

        Returns:
            The current Renderer instance.

        Raises:
            RendererNotBoundError: If not within AppEventLoop context.
        """
        return get_renderer_strict()

    def get_help_entries(self) -> list[tuple[str, str]]:
        """Derive help entries from ``@bind_action`` bindings.

        Panels using ``@bind_action`` inherit this; panels may still override
        for fully custom help. Multi-key actions render their keys joined
        with ``/``.
        """
        return derive_help_entries(self._action_bindings, self)

    def get_footer_entries(self) -> list[tuple[str, str]]:
        """Derive the compact footer subset (bindings with a ``tip``).

        Bindings sharing the same ``tip`` are merged into one entry with their
        keys joined, saving horizontal space (e.g. ``j/k/down/up Navigate``).
        ``tip_when`` may hide a tip for the current state; help (``desc``) is
        unaffected. State-dependent actions handled by ``capture_key``/
        ``handle_key`` (not ``@bind_action``) are intentionally absent — the
        footer shows the always-available, high-frequency keys.
        """
        grouped: dict[str, list[str]] = {}
        order: list[str] = []
        for binding in self._action_bindings:
            if binding.tip is None:
                continue
            if binding.tip_when is not None and not binding.tip_when(self):
                continue
            keys = resolve_action_keys(binding)
            if binding.tip not in grouped:
                grouped[binding.tip] = []
                order.append(binding.tip)
            grouped[binding.tip].extend(keys)
        return [("/".join(display_key(k) for k in grouped[tip]), tip) for tip in order]


def bind_signals(
    component: Component,
    *signals: Signal | Computed,
    callback: Callable[[], None] | None = None,
) -> Callable[[], None]:
    """Subscribe component to signals. Returns an unsubscribe function.

    Args:
        component: The component to refresh when signals change.
        *signals: One or more Signal/Computed instances to watch.
        callback: Optional handler. Defaults to component.refresh().

    Returns:
        Unsubscribe function. Caller must store and call on destroy.
    """
    import types

    cb = callback or component.refresh

    def _handler(self: Component, _: object) -> None:
        cb()

    bound = types.MethodType(_handler, component)
    # Keep bound alive as long as component is alive so WeakMethod
    # continues to resolve while the component exists.
    handlers: list[object] = getattr(component, "_bind_signal_handlers", [])
    handlers.append(bound)
    component._bind_signal_handlers = handlers

    unsubs: list[Callable[[], None]] = []
    for sig in signals:
        unsubs.append(sig.subscribe(bound))

    def unsubscribe() -> None:
        for unsub in unsubs:
            unsub()
        try:
            handlers.remove(bound)
        except ValueError:
            pass

    return unsubscribe


def resolve_focus_leaf(node: Component) -> Component:
    """Follow ``focus_child``, then drill layout children. Cycle-guarded.

    Does not return a focus-managing parent: a Column with ``focus_index``
    resolves to its focused child, not itself.
    """
    leaf = node
    visited: set[int] = set()
    while True:
        cid = id(leaf)
        if cid in visited:
            _logger.warning(
                "Cycle detected in focus_child chain at %s",
                type(leaf).__name__,
            )
            break
        visited.add(cid)

        child = leaf.focus_child
        if child is not None:
            leaf = child
            continue

        children = leaf.children
        if not children:
            break
        for nested in children:
            if nested.focus_child is not None or nested.children:
                leaf = nested
                break
        else:
            break
    return leaf


def resolve_presentation_leaf(node: Component | None) -> Component | None:
    """Follow ``presentation_child`` while not None. Cycle-guarded."""
    if node is None:
        return None
    seen: set[int] = set()
    while True:
        cid = id(node)
        if cid in seen:
            _logger.warning("Cycle in presentation_child chain")
            break
        seen.add(cid)
        child = node.presentation_child
        if child is None:
            break
        node = child
    return node
