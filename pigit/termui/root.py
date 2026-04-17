# -*- coding: utf-8 -*-
"""
Module: pigit/termui/root.py
Description: Internal framework root that wraps body + LayerStack.
Author: Zev
Date: 2026-04-17
"""

from __future__ import annotations

from typing import Optional, TYPE_CHECKING

from pigit.termui.components import Component
from pigit.termui.layer import LayerKind, LayerStack
from pigit.termui.overlay_kinds import OverlayDispatchResult, OverlayKind

if TYPE_CHECKING:
    from pigit.termui.surface import Surface
    from pigit.termui.overlay_kinds import OverlaySurface


class ComponentRoot(Component):
    """
    Internal framework root: wraps the user body component and manages overlays.
    Not exported in the public termui API.
    """

    NAME = "component_root"

    def __init__(self, body: Component) -> None:
        super().__init__()
        self._body = body
        self._body.parent = self
        self._layer_stack = LayerStack()
        self.overlay_kind = OverlayKind.NONE
        self._active_popup: Optional["OverlaySurface"] = None

    @property
    def body(self) -> Component:
        return self._body

    def _sync_overlay_state_from_stack(self) -> None:
        """Single source of truth: derive legacy host fields from LayerStack."""
        top = self._layer_stack.top(LayerKind.MODAL)
        self._active_popup = top
        self.overlay_kind = OverlayKind.POPUP if top is not None else OverlayKind.NONE

    # --- OverlayHost protocol (backward compatible with Popup/AlertDialog) ---

    def begin_popup_session(self, popup) -> None:
        self._layer_stack.push(LayerKind.MODAL, popup)
        self._sync_overlay_state_from_stack()

    def end_popup_session(self) -> None:
        """Release the top MODAL slot. Caller (Popup/AlertDialog) is responsible for hide()."""
        self._layer_stack.pop(LayerKind.MODAL)
        self._sync_overlay_state_from_stack()

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
        self._sync_overlay_state_from_stack()

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
        self._body._render_surface(surface)
        self._layer_stack.render(surface)

    def _handle_event(self, key: str) -> None:
        if self.has_overlay_open():
            result = self.try_dispatch_overlay(key)
            if result != OverlayDispatchResult.DROPPED_UNBOUND:
                return
        self._body._handle_event(key)

    def _expire_toasts(self) -> None:
        top = self._layer_stack.top(LayerKind.TOAST)
        if top is not None and top.is_expired():
            self._pop_layer(LayerKind.TOAST)

    def show_toast(self, message: str, duration: float = 2.0) -> "Toast":
        """Display a transient toast notification on the TOAST layer."""
        from pigit.termui.components_overlay import Toast

        toast = Toast(message, duration)
        self._layer_stack.push(LayerKind.TOAST, toast)
        return toast

    def show_sheet(self, child: Component, height: int = 8) -> "Sheet":
        """Display a bottom sheet on the SHEET layer."""
        from pigit.termui.components_overlay import Sheet

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
