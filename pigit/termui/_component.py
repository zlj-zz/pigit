"""
Module: pigit/termui/_component.py
Description: Base Component class and related utilities for the TUI framework.
Author: Zev
Date: 2026-04-19
"""

from __future__ import annotations

import contextvars
import logging
from abc import ABC
from dataclasses import dataclass
from typing import Any, TYPE_CHECKING
from collections.abc import Callable, Sequence

from ._bindings import (
    BindingsList,
    list_bindings,
    resolve_key_handlers_merged,
)
from ._runtime_context import (
    get_focus_manager,
    get_renderer,
    get_renderer_strict,
)
from .reactive import Computed, Signal
from .types import ActionEventType, OverlayDispatchResult

if TYPE_CHECKING:
    from ._renderer import Renderer
    from ._surface import Surface, _Subsurface

_logger = logging.getLogger(__name__)

NONE_SIZE = (0, 0)


@dataclass(eq=False)
class _Subscription:
    """Internal record tracking a framework-level event subscription."""

    action: ActionEventType
    handler: Callable[..., bool | None]
    pending: bool = True
    unsub: Callable[[], None] | None = None

    def cancel(self) -> None:
        if self.unsub is not None:
            self.unsub()


# Context variable for event-dispatch cycle detection during a single key event.
_event_dispatch_state: contextvars.ContextVar[dict | None] = contextvars.ContextVar(
    "_event_dispatch_state", default=None
)


class ComponentError(Exception):
    """Error class of ~Component."""


def _render_child_to_surface(
    component: Component, surface: Surface | _Subsurface, log_prefix: str
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

    Skeleton class containing tree structure, geometry, rendering,
    key handling, event bubbling, and lifecycle hooks.
    Subclasses must implement :meth:`_render_surface`.
    """

    BINDINGS: BindingsList | None = None

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

        self._key_handlers = resolve_key_handlers_merged(
            self, type(self), getattr(self, "BINDINGS", None)
        )
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
        action: ActionEventType,
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

    def _handle_event(self, key: str) -> bool:
        """Process a key event. Return True if consumed."""
        state = _event_dispatch_state.get()
        if state is None:
            state = {"visited": set()}
            token = _event_dispatch_state.set(state)
            try:
                return self._dispatch_event_impl(key, state)
            finally:
                _event_dispatch_state.reset(token)
        return self._dispatch_event_impl(key, state)

    def _dispatch_event_impl(self, key: str, state: dict) -> bool:
        """Internal event dispatch with cycle detection."""
        cid = id(self)
        if cid in state["visited"]:
            return False
        state["visited"].add(cid)

        # 1. Bindings (always consumed)
        handler = self._key_handlers.get(key)
        if handler is not None:
            handler()
            self._maybe_reestablish_focus()
            return True

        # 2. New bubbling-aware hook: handle_key -> bool
        handle_key = getattr(self, "handle_key", None)
        if handle_key is not None:
            if handle_key(key):
                self._maybe_reestablish_focus()
                return True

        # 3. Legacy hook: on_key (always consumed, no bubbling)
        on_key = getattr(self, "on_key", None)
        if on_key is not None and callable(on_key):
            on_key(key)
            self._maybe_reestablish_focus()
            return True

        # 4. Forward to event_target
        target = self.event_target
        if target is not None and id(target) not in state["visited"]:
            if target._handle_event(key):
                return True

        # 5. Bubble to parent
        if self.parent is not None:
            return self.parent._handle_event(key)

        return False

    def _maybe_reestablish_focus(self) -> None:
        """Re-establish focus chain if this component is the current leaf."""
        fm = get_focus_manager()
        if fm is None:
            return
        current_leaf = fm.get_focus_leaf()
        has_active_child = self.active_child is not None
        parent = self.parent
        parent_active = parent.active_child if parent is not None else None
        parent_switched = parent_active is not None and parent_active is not self
        if not has_active_child and not parent_switched and current_leaf is self:
            fm.set_focus_chain(self)

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

    def emit(self, action: ActionEventType, **data) -> None:
        """Bubble action up through parent chain to Application.

        Stops at the first ancestor whose ``on_event`` returns True.
        If no handler consumes it, logs a warning.
        """
        node = self.parent
        while node is not None:
            handler = getattr(node, "on_event", None)
            if callable(handler):
                if handler(action, **data):
                    return
            node = node.parent
        _logger.warning("Unhandled event %r from %s", action, type(self).__name__)

    def notify(self, action: ActionEventType, **data) -> None:
        """Notify all children by calling their ``update`` method."""
        for child in self.children:
            update_fn = getattr(child, "update", None)
            if callable(update_fn):
                update_fn(action, **data)

    def accept(self, action: ActionEventType, **data) -> None:
        """Handle an action event broadcast from a parent container.

        Default is no-op; container components override this to route or
        broadcast to children.
        """

    def update(self, action: ActionEventType, **data) -> None:
        """Receive an action update from a parent or sibling component.

        Default is no-op; interactive components override this to react to
        state changes (e.g. a panel refreshing when another panel changes).
        """

    @property
    def active_child(self) -> Component | None:
        """Return the currently active child component, or ``None``.

        Reads the ``active`` attribute if it exists and is a Component.
        This provides a safe, type-checked alternative to
        ``getattr(obj, "active", None)`` probes.
        """
        active = getattr(self, "active", None)
        return active if isinstance(active, Component) else None

    @property
    def presented_child(self) -> Component | None:
        """Child that represents this container for external UI (help, inspector).

        None means this container presents itself.
        Containers with an active sub-panel override this.
        """
        return None

    @property
    def event_target(self) -> Component | None:
        """Child to which unhandled events are forwarded.

        None means events bubble to parent instead.
        """
        return None

    @property
    def is_focus_leaf(self) -> bool:
        """Return True if this component should render as focused."""
        if self._focus_level == 0:
            return True
        # Container transparency: if an ancestor presents this component as its
        # delegate child, treat this component as focused.
        node = self.parent
        while node is not None:
            if node.presented_child is self and node._focus_level >= 0:
                return True
            node = node.parent
        return False

    def find_focus_leaf(self) -> Component:
        """Walk down the tree to find the deepest focusable leaf.

        Follows :meth:`active_child` and :attr:`presented_child` when available
        and drills into :attr:`children` for layout containers that do not
        manage an active child.

        .. warning::
            This method walks via :meth:`active_child`, :attr:`presented_child`,
            and :attr:`children`. Passing a ``MagicMock`` (or any object that
            returns a new object for every attribute access) will cause an
            infinite loop because ``active_child`` and ``children`` never
            resolve to ``None`` / empty. Tests that create a ``ComponentRoot``
            must use a real ``Component`` instance as the ``body`` argument.
        """
        leaf = self
        visited: set[int] = set()
        while True:
            cid = id(leaf)
            if cid in visited:
                _logger.warning(
                    "Cycle detected in presented_child/active_child chain at %s",
                    type(leaf).__name__,
                )
                break
            visited.add(cid)

            presented = leaf.presented_child
            if presented is not None:
                leaf = presented
                continue

            active = leaf.active_child
            if active is not None:
                leaf = active
                continue

            children = leaf.children
            if children:
                for child in children:
                    if (
                        child.presented_child is not None
                        or child.active_child is not None
                    ):
                        leaf = child
                        break
                    if child.children:
                        leaf = child
                        break
                else:
                    break
            else:
                break
        # If leaf is nested inside a focus-managed container, return the
        # container so that the framework routes events to it (not the leaf).
        parent = leaf.parent
        if (
            parent is not None
            and parent.presented_child is leaf
            and parent.event_target is leaf
        ):
            return parent
        return leaf

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


def _truncate_help_line(text: str, max_len: int = 120) -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - 1] + "…"


def _default_help_entries(component: Component) -> list[tuple[str, str]]:
    cls = type(component)
    rows: list[tuple[str, str]] = []
    for semantic_key, target in list_bindings(component, cls)[:64]:
        desc = _describe_binding_target(component, target)
        rows.append((semantic_key, _truncate_help_line(desc)))
    return rows


def _describe_binding_target(
    owner: Component,
    target: str | Callable[..., object],
) -> str:
    if isinstance(target, str):
        fn = getattr(owner, target, None)
        if callable(fn):
            doc = getattr(fn, "__doc__", None)
            if doc and doc.strip():
                return doc.strip().splitlines()[0].strip()
        return f"{target} action"
    return "bound command"


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


def resolve_presented(component: Component | None) -> Component | None:
    """Walk the presented_child chain to find the outermost presented component.

    Used for help text, inspector data, and other external queries that should
    penetrate container wrappers.
    """
    seen: set[int] = set()
    while component is not None:
        cid = id(component)
        if cid in seen:
            _logger.warning("Cycle in presented_child chain")
            break
        seen.add(cid)
        presented = component.presented_child
        if presented is None:
            break
        component = presented
    return component


def _proxy_to_presented(component: Component, method_name: str, *, default=None):
    """Call method on component's presented_child if available."""
    child = resolve_presented(component)
    if child is not None and child is not component:
        method = getattr(child, method_name, None)
        if callable(method):
            return method()
    return default
