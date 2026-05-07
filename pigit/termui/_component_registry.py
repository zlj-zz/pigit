# -*- coding: utf-8 -*-
"""
Module: pigit/termui/_component_registry.py
Description: ContextVar-based component registry for id-based O(1) lookup.
Author: Zev
Date: 2026-05-07
"""

from __future__ import annotations

import contextvars
import logging
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from ._component_base import Component

_logger = logging.getLogger(__name__)

_registry_ctx: contextvars.ContextVar[Optional["ComponentRegistry"]] = (
    contextvars.ContextVar("registry", default=None)
)


class ComponentRegistry:
    """Id-based component registry for O(1) lookup within a component tree."""

    def __init__(self) -> None:
        self._by_id: dict[str, "Component"] = {}

    def register(self, component: "Component") -> None:
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

    def unregister(self, component: "Component") -> None:
        if component.id:
            self._by_id.pop(component.id, None)

    def by_id(self, id: str) -> Optional["Component"]:
        return self._by_id.get(id)


def get_registry() -> Optional[ComponentRegistry]:
    """Get current registry from context."""
    return _registry_ctx.get()


def by_id(id: str) -> Optional["Component"]:
    """Find component by its unique identifier in the current registry context."""
    reg = get_registry()
    return reg.by_id(id) if reg else None
