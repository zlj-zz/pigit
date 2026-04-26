# -*- coding: utf-8 -*-
"""
Module: pigit/termui/_overlay_context.py
Description: Overlay host context management (Toast/Sheet) via ContextVar.
Author: Zev
Date: 2026-04-25
"""

from __future__ import annotations

import contextvars
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ._component_base import Component
    from ._overlay_components import Sheet, Toast
    from .types import ToastPosition

_overlay_host_ctx: contextvars.ContextVar[Optional["Component"]] = (
    contextvars.ContextVar("overlay_host", default=None)
)


def set_overlay_host(host: "Component") -> contextvars.Token:
    """Set the current overlay host in context."""
    return _overlay_host_ctx.set(host)


def reset_overlay_host(token: contextvars.Token) -> None:
    """Reset overlay host context to previous value."""
    _overlay_host_ctx.reset(token)


def _get_host() -> Optional["Component"]:
    """Get the current overlay host from context."""
    return _overlay_host_ctx.get()


def show_toast(
    message: str,
    *,
    duration: float = 2.0,
    position: Optional[ToastPosition] = None,
) -> Optional["Toast"]:
    """Display a transient toast notification via the current overlay host."""
    host = _get_host()
    if host is None:
        return None
    return host.show_toast(message, duration=duration, position=position)


def show_sheet(child: "Component", height: int = 8) -> Optional["Sheet"]:
    """Display a bottom sheet via the current overlay host."""
    host = _get_host()
    if host is None:
        return None
    return host.show_sheet(child, height)
