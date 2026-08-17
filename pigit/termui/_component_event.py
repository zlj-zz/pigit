"""
Module: pigit/termui/_component_event.py
Description: Keyboard event routing algorithm for the component tree.
    Pure functions that operate on a Component — no state held here
    beyond the cycle-detection ContextVar.

    Dispatch layers (first match wins):
        capture_key → bindings → handle_key → parent bubble.
    TabView._handle_event may still forward to its active child (not
    this algorithm). Overlay and app-level keys are dispatched by
    ComponentRoot before this algorithm runs on the focus leaf.

Author: Zev
Date: 2026-06-15
"""

from __future__ import annotations

import contextvars
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ._component import Component
    from .types import EventType

_logger = logging.getLogger(__name__)

# Context variable for event-dispatch cycle detection during a single key event.
_event_dispatch_state: contextvars.ContextVar[dict | None] = contextvars.ContextVar(
    "_event_dispatch_state", default=None
)


def dispatch_key(component: Component, key: str) -> bool:
    """Route a key event through the component tree with cycle detection.

    Entry point called by ``Component._handle_event()``.
    Sets up the cycle-detection ContextVar scope, then delegates to the
    4-layer dispatch algorithm.

    Args:
        component: The component receiving the key event.
        key: Semantic key string.

    Returns:
        True if the key was consumed, False otherwise.
    """
    state = _event_dispatch_state.get()
    if state is None:
        state = {"visited": set()}
        token = _event_dispatch_state.set(state)
        try:
            return _dispatch_impl(component, key, state)
        finally:
            _event_dispatch_state.reset(token)
    return _dispatch_impl(component, key, state)


def _dispatch_impl(component: Component, key: str, state: dict) -> bool:
    """4-layer priority dispatch with cycle detection.

    Layers (first match wins):
        0. ``capture_key(key) -> bool`` hook (intercept before bindings)
        1. Key bindings (``_key_handlers``) — always consumed
        2. ``handle_key(key) -> bool`` hook (new-style, can bubble)
        3. Bubble to ``parent``
    """
    cid = id(component)
    if cid in state["visited"]:
        return False
    state["visited"].add(cid)

    capture = getattr(component, "capture_key", None)
    if capture is not None and capture(key):
        _maybe_reestablish_focus(component)
        return True

    handler = component._key_handlers.get(key)
    if handler is not None:
        handler()
        _maybe_reestablish_focus(component)
        return True

    handle_key = getattr(component, "handle_key", None)
    if handle_key is not None:
        if handle_key(key):
            _maybe_reestablish_focus(component)
            return True

    if component.parent is not None:
        return component.parent._handle_event(key)

    return False


def _maybe_reestablish_focus(component: Component) -> None:
    """After a consumed key, re-resolve focus if *component* is on the chain.

    If *component* is the current leaf or an ancestor of it, set the chain
    to ``resolve_focus_leaf(component)``. Same-leaf is a no-op.
    """
    from ._component import resolve_focus_leaf
    from ._runtime_context import get_focus_manager

    fm = get_focus_manager()
    if fm is None:
        return
    current_leaf = fm.get_focus_leaf()
    if current_leaf is None:
        return
    node: Component | None = current_leaf
    while node is not None:
        if node is component:
            fm.set_focus_chain(resolve_focus_leaf(component))
            return
        node = node.parent


def bubble_event(component: Component, action: EventType, **data) -> None:
    """Bubble an action event up through the parent chain.

    Stops at the first ancestor whose ``on_event`` returns True.
    If no handler consumes the event, logs a warning.

    Args:
        component: The component that originates the event.
        action: Action event type.
        **data: Arbitrary keyword data forwarded to handlers.
    """
    node = component.parent
    while node is not None:
        handler = getattr(node, "on_event", None)
        if callable(handler):
            if handler(action, **data):
                return
        node = node.parent
    _logger.warning("Unhandled event %r from %s", action, type(component).__name__)


def notify_children(component: Component, action: EventType, **data) -> None:
    """Notify all direct children by calling their ``update`` method.

    Children that do not implement ``update`` are silently skipped.

    Args:
        component: The parent component whose children are notified.
        action: Action event type.
        **data: Arbitrary keyword data forwarded to each child.
    """
    for child in component.children:
        update_fn = getattr(child, "update", None)
        if callable(update_fn):
            update_fn(action, **data)
