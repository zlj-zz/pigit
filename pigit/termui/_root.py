# -*- coding: utf-8 -*-
"""
Module: pigit/termui/_root.py
Description: Internal framework root that wraps body + LayerStack.
Author: Zev
Date: 2026-04-19
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Optional

from ._component_base import Component, _set_focus_chain
from ._layer import LayerKind, LayerStack
from .types import OverlayDispatchResult, ToastPosition
from . import _overlay_context

if TYPE_CHECKING:
    from ._overlay_components import Sheet, Toast
    from ._surface import Surface

_logger = logging.getLogger(__name__)


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
        self._overlay_host_token = _overlay_context.set_overlay_host(self)
        self._badge_text: Optional[str] = None
        self._badge_bg: Optional[tuple[int, int, int]] = None
        self._badge_fg: Optional[tuple[int, int, int]] = None
        self._badge_until = 0

    def destroy(self) -> None:
        """Clean up overlay host token. Call when the TUI exits."""
        try:
            _overlay_context.reset_overlay_host(self._overlay_host_token)
        except (RuntimeError, ValueError):
            _logger.error("Failed to reset overlay host token", exc_info=True)

    @property
    def body(self) -> Component:
        """The root's single child component (the application body)."""
        return self._body

    # --- Badge API (framework-managed, not an overlay) ---

    def show_badge(
        self,
        text: str,
        duration: Optional[float] = None,
        bg: Optional[tuple[int, int, int]] = None,
        fg: Optional[tuple[int, int, int]] = None,
    ) -> None:
        """Set badge text to display in the chrome header.

        The badge is rendered by the application chrome (e.g. Header)
        reading ``self.parent.badge_text``.  This method only stores state;
        the framework does not control layout.

        Args:
            text: Badge text to display.
            duration: Seconds until auto-hide. ``None`` means permanent.
        """
        self._badge_text = text
        self._badge_bg = bg
        self._badge_fg = fg
        self._badge_until = (
            time.monotonic() + duration
            if duration is not None and duration > 0
            else float("inf")
        )

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

    # --- OverlayHost protocol ---

    def has_overlay_open(self) -> bool:
        """Return True if any overlay (modal, toast, or sheet) is currently open."""
        return self._layer_stack.has_any_open()

    def try_dispatch_overlay(self, key: str) -> OverlayDispatchResult:
        """Dispatch a keypress to the active overlay, if any."""
        return self._layer_stack.dispatch(key)

    def force_close_overlay_after_error(self) -> None:
        """Forcibly close the top modal overlay, used for error recovery."""
        top = self._layer_stack.pop(LayerKind.MODAL)
        if top is not None and hasattr(top, "hide"):
            top.hide()
            reset = getattr(top, "reset_state", None)
            if callable(reset):
                reset()

    # --- Component lifecycle ---

    def refresh(self) -> None:
        """No-op for the root; body and overlays are refreshed independently."""
        pass

    def accept(self, action, **data):
        """Forward an action to the body component."""
        self._body.accept(action, **data)

    def resize(self, size: tuple[int, int]) -> None:
        """Resize the body and all active overlays to the new terminal size."""
        self._body.resize(size)
        self._layer_stack.resize(size)
        super().resize(size)

    def _render_surface(self, surface: "Surface") -> None:
        self._expire_toasts()
        self._expire_badge()
        self._body._render_surface(surface)
        self._layer_stack.render(surface)

    def _find_focus_leaf(self, start: Optional[Component] = None) -> Component:
        """Walk down the component tree to find the deepest focusable leaf.

        Follows ``active`` when available (TabView) and drills into ``children``
        for layout containers (Column, Row) that do not define ``active``.
        """
        leaf = start if start is not None else self._body
        while True:
            active = getattr(leaf, "active", None)
            if active is not None:
                leaf = active
                continue
            children = getattr(leaf, "children", None)
            if children:
                for child in children:
                    if getattr(child, "active", None) is not None:
                        leaf = child
                        break
                    if getattr(child, "children", None):
                        leaf = child
                        break
                else:
                    break
            else:
                break
        return leaf

    def _top_open_overlay(self) -> Optional[Component]:
        for kind in (LayerKind.MODAL, LayerKind.SHEET):
            top = self._layer_stack.top(kind)
            if top is not None and getattr(top, "open", False):
                return top
        return None

    def _handle_event(self, key: str) -> None:
        result = self.try_dispatch_overlay(key)
        if result != OverlayDispatchResult.DROPPED_UNBOUND:
            top = self._top_open_overlay()
            if top is not None:
                _set_focus_chain(top)
            else:
                _set_focus_chain(self._find_focus_leaf())
            return
        self._body._handle_event(key)
        top = self._top_open_overlay()
        if top is not None:
            _set_focus_chain(top)

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
