# -*- coding: utf-8 -*-
"""
Module: pigit/termui/types.py
Description: Base types, enums, and protocols (no runtime dependencies).
Author: Zev
Date: 2026-04-19
"""

from __future__ import annotations

from enum import Enum, auto
from typing import Protocol, runtime_checkable


# Action types
class ActionLiteral(Enum):
    goto = auto()


# Toast positions
class ToastPosition(Enum):
    """Toast display position."""

    TOP_LEFT = auto()
    TOP_RIGHT = auto()
    BOTTOM_LEFT = auto()
    BOTTOM_RIGHT = auto()


# Layer kinds (merged from LayerKind and OverlayKind)
class LayerKind(Enum):
    """Layer kind for overlay management."""

    NONE = 0
    MODAL = 1  # Formerly POPUP (value 1), renamed to MODAL while keeping the value
    TOAST = 2
    SHEET = 3


# Overlay key dispatch results
class OverlayDispatchResult(Enum):
    """Result of overlay key dispatch."""

    HANDLED_EXPLICIT = auto()
    HANDLED_IMPLICIT = auto()
    DROPPED_UNBOUND = auto()
    CLOSED_AFTER_ERROR = auto()  # Error recovery: slot cleared, host cleaned up


# Overlay surface protocol
class OverlaySurface(Protocol):
    """
    Modal shell that may occupy a MODAL slot on a ComponentRoot via LayerStack.

    Popup and AlertDialog satisfy this protocol structurally.
    Other implementations may be introduced without subclassing Popup.
    """

    open: bool

    def dispatch_overlay_key(self, key: str) -> OverlayDispatchResult:
        """Route one key for this modal (shell, then child, then fallback)."""

    def hide(self) -> None:
        """Release visible state for this shell."""

    def _render_surface(self, surface: SurfaceProtocol) -> None:
        """Render this shell into the given Surface when active."""


# Surface protocol (distinguished from the Surface implementation class)
@runtime_checkable
class SurfaceProtocol(Protocol):
    """Surface protocol for type checking."""

    @property
    def width(self) -> int: ...

    @property
    def height(self) -> int: ...

    def draw_text(self, row: int, col: int, text: str) -> None: ...

    def subsurface(self, x: int, y: int, w: int, h: int) -> SurfaceProtocol: ...
