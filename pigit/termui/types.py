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


# 动作类型
class ActionLiteral(Enum):
    goto = auto()


# 按键路由策略
class KeyRouting(Enum):
    child_first = auto()
    switch_first = auto()


# Toast 位置
class ToastPosition(Enum):
    """Toast display position."""
    TOP_LEFT = auto()
    TOP_RIGHT = auto()
    BOTTOM_LEFT = auto()
    BOTTOM_RIGHT = auto()


# 图层类型（合并原 LayerKind 和 OverlayKind）
class LayerKind(Enum):
    """Layer kind for overlay management."""
    NONE = 0
    MODAL = 1  # 原 POPUP（值为1）直接更名为 MODAL，保持值不变
    TOAST = 2
    SHEET = 3


# 覆盖层按键分发结果
class OverlayDispatchResult(Enum):
    """Result of overlay key dispatch."""
    HANDLED_EXPLICIT = auto()
    HANDLED_IMPLICIT = auto()
    DROPPED_UNBOUND = auto()
    CLOSED_AFTER_ERROR = auto()  # Error recovery: slot cleared, host cleaned up


# 覆盖层表面协议
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


# Surface Protocol（与实现类 Surface 区分）
@runtime_checkable
class SurfaceProtocol(Protocol):
    """Surface protocol for type checking."""

    @property
    def width(self) -> int: ...

    @property
    def height(self) -> int: ...

    def draw_text(self, row: int, col: int, text: str) -> None: ...

    def subsurface(self, x: int, y: int, w: int, h: int) -> SurfaceProtocol: ...
