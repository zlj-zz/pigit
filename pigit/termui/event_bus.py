"""
Module: pigit/termui/event_bus.py
Description: Framework-level pub/sub event bus for cross-panel coordination.
Author: Zev
Date: 2026-06-04
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field

from .types import ActionEventType

_logger = logging.getLogger(__name__)

EventHandler = Callable[..., bool | None]


@dataclass
class EventBus:
    """Framework-level pub/sub bus supporting multiple subscribers per event."""

    _handlers: dict[ActionEventType, list[EventHandler]] = field(default_factory=dict)

    def subscribe(
        self, action: ActionEventType, handler: EventHandler
    ) -> Callable[[], None]:
        """Register a handler for an action. Returns an unsubscribe callback."""
        self._handlers.setdefault(action, []).append(handler)

        def unsubscribe() -> None:
            try:
                self._handlers[action].remove(handler)
            except (ValueError, KeyError):
                pass

        return unsubscribe

    def publish(self, action: ActionEventType, **data) -> bool:
        """Dispatch an event to all subscribers. Returns True if any handler consumed it."""
        handled = False
        for handler in list(self._handlers.get(action, ())):
            try:
                if handler(**data):
                    handled = True
            except Exception:
                _logger.exception("Event handler failed for %r", action)
        return handled

    def clear(self) -> None:
        """Remove all subscribers. Useful for lifecycle cleanup."""
        self._handlers.clear()
