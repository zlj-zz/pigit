"""
Module: pigit/termui/types.py
Description: Base types, enums, and protocols (no runtime dependencies).
Author: Zev
Date: 2026-04-19
"""

from __future__ import annotations

from enum import Enum, auto
from typing import ClassVar, Protocol, runtime_checkable

# ---------------------------------------------------------------------------
# EventType — unified event identifier
# ---------------------------------------------------------------------------


class EventType:
    """Unified event identifier. Framework built-ins and user-defined events
    are all instances of this type. Same-name instances are globally unique
    (singleton per name), so events can be shared across modules without
    explicit import.
    """

    _registry: ClassVar[dict[str, EventType]] = {}
    _name: str

    def __new__(cls, name: str) -> EventType:
        if name in cls._registry:
            return cls._registry[name]
        instance = super().__new__(cls)
        instance._name = name
        cls._registry[name] = instance
        return instance

    def __init__(self, name: str) -> None:
        pass  # __new__ handles creation

    def __eq__(self, other: object) -> bool:
        return isinstance(other, EventType) and self._name == other._name

    def __hash__(self) -> int:
        return hash(self._name)

    def __repr__(self) -> str:
        return f"EventType({self._name!r})"

    @property
    def name(self) -> str:
        return self._name


# Framework built-in events
EVT_GOTO = EventType("goto")
EVT_SELECTION_CHANGED = EventType("selection_changed")


# ---------------------------------------------------------------------------
# Toast positions
# ---------------------------------------------------------------------------


class ToastPosition(Enum):
    """Toast display position."""

    TOP_LEFT = auto()
    TOP_RIGHT = auto()
    BOTTOM_LEFT = auto()
    BOTTOM_RIGHT = auto()


# ---------------------------------------------------------------------------
# Layer kinds
# ---------------------------------------------------------------------------


class LayerKind(Enum):
    """Layer kind for overlay management."""

    NONE = 0
    MODAL = 1
    TOAST = 2
    SHEET = 3


# ---------------------------------------------------------------------------
# Overlay key dispatch results
# ---------------------------------------------------------------------------


class OverlayDispatchResult(Enum):
    """Result of overlay key dispatch."""

    HANDLED_EXPLICIT = auto()
    HANDLED_IMPLICIT = auto()
    DROPPED_UNBOUND = auto()
    CLOSED_AFTER_ERROR = auto()


# ---------------------------------------------------------------------------
# Protocols
# ---------------------------------------------------------------------------


class OverlaySurface(Protocol):
    """Modal shell that may occupy a MODAL slot on a ComponentRoot."""

    open: bool

    def dispatch_overlay_key(self, key: str) -> OverlayDispatchResult: ...

    def hide(self) -> None: ...

    def _render_surface(self, surface: SurfaceProtocol) -> None: ...


@runtime_checkable
class PreviewPayload(Protocol):
    """Side-preview data source for Status/Stash-style panels."""

    def preview_title(self) -> str: ...

    def preview_lines(self) -> list[str]: ...


@runtime_checkable
class SurfaceProtocol(Protocol):
    """Surface protocol for type checking."""

    @property
    def width(self) -> int: ...

    @property
    def height(self) -> int: ...

    def draw_text(self, row: int, col: int, text: str) -> None: ...

    def subsurface(self, x: int, y: int, w: int, h: int) -> SurfaceProtocol: ...
