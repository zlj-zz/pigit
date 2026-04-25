# -*- coding: utf-8 -*-
"""
Module: pigit/termui/_root.py
Description: Internal framework root that wraps body + LayerStack.
Author: Zev
Date: 2026-04-19
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Optional

from ._component_base import Component
from ._layer import LayerKind, LayerStack
from .types import OverlayDispatchResult, ToastPosition

if TYPE_CHECKING:
    from ._overlay_components import Sheet, Toast
    from ._surface import Surface


class ComponentRoot(Component):
    """
    Internal framework root: wraps the user body component and manages overlays.
    Not exported in the public termui API.
    """

    def __init__(self, body: Component) -> None:
        super().__init__()
        self._body = body
        self._body.parent = self
        self._layer_stack = LayerStack()
        self._badge_text: Optional[str] = None

    @property
    def body(self) -> Component:
        return self._body

    # --- Badge API (framework-managed, not an overlay) ---

    def show_badge(
        self,
        text: str,
        duration: float = 0,
        bg: Optional[tuple[int, int, int]] = None,
        fg: Optional[tuple[int, int, int]] = None,
    ) -> None:
        """Set badge text to display in the chrome header.

        The badge is rendered by the application chrome (e.g. AppHeader)
        reading ``self.parent.badge_text``.  This method only stores state;
        the framework does not control layout.
        """
        self._badge_text = text
        self._badge_bg = bg
        self._badge_fg = fg
        self._badge_until = time.monotonic() + duration if duration > 0 else float("inf")

    def hide_badge(self) -> None:
        """Clear the badge text."""
        self._badge_text = None
        self._badge_bg = None
        self._badge_fg = None
        self._badge_until = 0

    @property
    def badge_text(self) -> Optional[str]:
        """Current badge text, or ``None`` if hidden."""
        return self._badge_text

    @property
    def badge_bg(self) -> Optional[tuple[int, int, int]]:
        """Current badge background color, or ``None`` if hidden."""
        return self._badge_bg

    @property
    def badge_fg(self) -> Optional[tuple[int, int, int]]:
        """Current badge foreground color, or ``None`` if hidden."""
        return self._badge_fg

    # --- OverlayHost protocol (backward compatible with Popup/AlertDialog) ---

    def begin_popup_session(self, popup) -> None:
        self._layer_stack.push(LayerKind.MODAL, popup)

    def end_popup_session(self) -> None:
        """Release the top MODAL slot. Caller (Popup/AlertDialog) is responsible for hide()."""
        self._layer_stack.pop(LayerKind.MODAL)

    def has_overlay_open(self) -> bool:
        return self._layer_stack.has_any_open()

    def try_dispatch_overlay(self, key: str) -> OverlayDispatchResult:
        return self._layer_stack.dispatch(key)

    def force_close_overlay_after_error(self) -> None:
        top = self._layer_stack.pop(LayerKind.MODAL)
        if top is not None and hasattr(top, "hide"):
            top.hide()
            reset = getattr(top, "reset_state", None)
            if callable(reset):
                reset()

    # --- Component lifecycle ---

    def fresh(self) -> None:
        pass

    def accept(self, action, **data):
        self._body.accept(action, **data)

    def resize(self, size: tuple[int, int]) -> None:
        self._body.resize(size)
        self._layer_stack.resize(size)
        super().resize(size)

    def _render_surface(self, surface: "Surface") -> None:
        self._expire_toasts()
        self._expire_badge()
        self._body._render_surface(surface)
        self._layer_stack.render(surface)

    def _handle_event(self, key: str) -> None:
        if self.has_overlay_open():
            result = self.try_dispatch_overlay(key)
            if result != OverlayDispatchResult.DROPPED_UNBOUND:
                return
        self._body._handle_event(key)

    def _expire_badge(self) -> None:
        if getattr(self, "_badge_until", 0) and time.monotonic() > self._badge_until:
            self.hide_badge()

    def _expire_toasts(self) -> None:
        top = self._layer_stack.top(LayerKind.TOAST)
        if top is not None and top.is_expired():
            self._pop_layer(LayerKind.TOAST)

    def show_toast(
        self,
        message: str,
        duration: float = 2.0,
        position: Optional[ToastPosition] = None,
    ) -> "Toast":
        """Display a transient toast notification on the TOAST layer.

        Args:
            message: Toast message content.
            duration: Display duration in seconds.
            position: ToastPosition enum value (None for default TOP_RIGHT).

        Returns:
            Toast instance.
        """
        from pigit.termui._overlay_components import Toast

        existing = self._layer_stack.top(LayerKind.TOAST)
        if existing is not None:
            self._pop_layer(LayerKind.TOAST)

        if position is None:
            position = ToastPosition.TOP_RIGHT

        toast = Toast(message, duration=duration, position=position)
        toast.resize(self._size)
        self._layer_stack.push(LayerKind.TOAST, toast)
        return toast

    def show_sheet(self, child: Component, height: int = 8) -> "Sheet":
        """Display a bottom sheet on the SHEET layer."""
        from pigit.termui._overlay_components import Sheet

        sheet = Sheet(child, height)
        sheet.resize(self._size)
        self._layer_stack.push(LayerKind.SHEET, sheet)
        return sheet

    def dismiss_toast(self) -> None:
        """Dismiss the current toast, if any."""
        self._pop_layer(LayerKind.TOAST)

    def dismiss_sheet(self) -> None:
        """Dismiss the current sheet, if any."""
        self._pop_layer(LayerKind.SHEET)

    def _pop_layer(self, kind: LayerKind) -> None:
        overlay = self._layer_stack.pop(kind)
        if overlay is not None:
            overlay.hide()
