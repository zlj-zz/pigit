"""
Module: pigit/termui/_component_event.py
Description: Keyboard event routing algorithm for the component tree.
    Pure functions that operate on a Component — no state held here
    beyond the cycle-detection ContextVar.

    Extracted from ``_component.py`` so the 5-layer dispatch logic
    (capture_key → bindings → handle_key → event_target → parent bubble)
    can be understood and tested independently.

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
    5-layer dispatch algorithm.

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
    """5-layer priority dispatch with cycle detection.

    Layers (first match wins):
        0. ``capture_key(key) -> bool`` hook (intercept before bindings)
        1. Key bindings (``_key_handlers``) — always consumed
        2. ``handle_key(key) -> bool`` hook (new-style, can bubble)
        3. Forward to ``event_target`` child
        4. Bubble to ``parent``
    """
    cid = id(component)
    if cid in state["visited"]:
        return False
    state["visited"].add(cid)

    # 0. Capture hook: intercept keys before bindings (e.g. an active text filter)
    capture = getattr(component, "capture_key", None)
    if capture is not None and capture(key):
        _maybe_reestablish_focus(component)
        return True

    # 1. Bindings (always consumed)
    handler = component._key_handlers.get(key)
    if handler is not None:
        handler()
        _maybe_reestablish_focus(component)
        return True

    # 2. Bubbling-aware hook: handle_key -> bool
    handle_key = getattr(component, "handle_key", None)
    if handle_key is not None:
        if handle_key(key):
            _maybe_reestablish_focus(component)
            return True

    # 3. Forward to event_target
    target = component.event_target
    if target is not None and id(target) not in state["visited"]:
        if target._handle_event(key):
            return True

    # 4. Bubble to parent
    if component.parent is not None:
        return component.parent._handle_event(key)

    return False


def _maybe_reestablish_focus(component: Component) -> None:
    """Re-establish focus chain if *component* is the current leaf.

    Called after a key binding or hook consumes a key, in case the
    handler changed the component tree state.
    """
    from ._runtime_context import get_focus_manager

    fm = get_focus_manager()
    if fm is None:
        return
    current_leaf = fm.get_focus_leaf()
    has_active_child = component.active_child is not None
    parent = component.parent
    parent_active = parent.active_child if parent is not None else None
    parent_switched = parent_active is not None and parent_active is not component
    if not has_active_child and not parent_switched and current_leaf is component:
        fm.set_focus_chain(component)


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
