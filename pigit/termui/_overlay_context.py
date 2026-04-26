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
    from ._root import ComponentRoot
    from .types import ToastPosition

_overlay_host_ctx: contextvars.ContextVar[Optional["ComponentRoot"]] = (
    contextvars.ContextVar("overlay_host", default=None)
)


def set_overlay_host(host: "ComponentRoot") -> contextvars.Token:
    """Set the current overlay host in context."""
    return _overlay_host_ctx.set(host)


def reset_overlay_host(token: contextvars.Token) -> None:
    """Reset overlay host context to previous value."""
    _overlay_host_ctx.reset(token)


def _get_host() -> Optional["ComponentRoot"]:
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


def show_badge(
    text: str,
    duration: Optional[float] = None,
    bg: Optional[tuple[int, int, int]] = None,
    fg: Optional[tuple[int, int, int]] = None,
) -> None:
    """Show a badge on the overlay host."""
    host = _get_host()
    if host is None:
        return
    host.show_badge(text, duration=duration, bg=bg, fg=fg)


def get_badge() -> tuple[
    Optional[str],
    Optional[tuple[int, int, int]],
    Optional[tuple[int, int, int]],
]:
    """Get current badge state from the overlay host.

    Returns:
        Tuple of (badge_text, badge_bg, badge_fg). All None if no badge
        or no host is active.
    """
    host = _get_host()
    if host is None:
        return None, None, None
    return host.badge_text, host.badge_bg, host.badge_fg
