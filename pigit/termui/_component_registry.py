"""
Module: pigit/termui/_component_registry.py
Description: ContextVar-based component registry for id-based O(1) lookup.
Author: Zev
Date: 2026-05-07
"""

from __future__ import annotations

import contextvars
import logging
from typing import TypeVar, cast

from ._component_base import Component

_logger = logging.getLogger(__name__)

T = TypeVar("T", bound=Component)

_registry_ctx: contextvars.ContextVar[ComponentRegistry | None] = (
    contextvars.ContextVar("registry", default=None)
)


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


def get_registry() -> ComponentRegistry | None:
    """Get current registry from context."""
    return _registry_ctx.get()


def by_id(id: str, expect_type: type[T] | None = None) -> T | None:
    """Find component by its unique identifier in the current registry context.

    Args:
        id: Component identifier.
        expect_type: Optional expected component type. If the found component
            is not an instance of this type, raises TypeError.

    Returns:
        The component instance, or None if not found.

    Raises:
        TypeError: If expect_type is given and the found component mismatches.
    """
    reg = get_registry()
    comp = reg.by_id(id) if reg else None
    if comp is None:
        return None
    if expect_type is not None and not isinstance(comp, expect_type):
        raise TypeError(
            f"Component {id!r} is {type(comp).__name__}, expected {expect_type.__name__}"
        )
    return cast(T, comp)
