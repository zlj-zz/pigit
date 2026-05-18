"""
Module: pigit/termui/_root.py
Description: Internal framework root that wraps body + LayerStack.
Author: Zev
Date: 2026-04-19
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING
from collections.abc import Callable, Sequence

from ._component import Component
from ._layer import LayerKind, LayerStack
from .types import OverlayDispatchResult, ToastPosition
from ._runtime_context import (
    FocusManager,
    get_badge_signal,
)

if TYPE_CHECKING:
    from ._runtime_context import ComponentRegistry
    from ._segment import Segment
    from ._surface import Surface, _Subsurface
    from .widgets import Sheet, Toast


class ComponentRoot(Component):
    """
    Internal framework root: wraps the user body component and manages overlays.
    Not exported in the public termui API.
    """

    def __init__(
        self,
        body: Component,
        registry: ComponentRegistry | None = None,
    ) -> None:
        super().__init__()
        self._body = body
        self._body.parent = self
        self._registry = registry
        self._layer_stack = LayerStack()
        self._focus_manager = FocusManager(self)
        self._focus_manager.sync_focus_to_overlay_or_leaf()
        self._badge_text: str | None = None
        self._badge_bg: tuple[int, int, int] | None = None
        self._badge_fg: tuple[int, int, int] | None = None
        self._badge_until = 0
        self._app_on_event: Callable | None = None

    def destroy(self) -> None:
        """Destroy children. Runtime context is reset by the caller."""
        self._body.destroy()
        super().destroy()

    def sync_focus_after_app_binding(self, overlay_was_open: bool) -> None:
        """Restore focus to body leaf when an app binding closes an overlay."""
        self._focus_manager.sync_focus_if_overlay_closed(
            overlay_was_open, self.has_overlay_open()
        )

    @property
    def body(self) -> Component:
        """The root's single child component (the application body)."""
        return self._body

    # --- Badge API (framework-managed, not an overlay) ---

    def on_event(self, action, **data) -> bool:
        """Delegate unhandled events to the Application handler, if set."""
        if self._app_on_event is not None:
            return self._app_on_event(action, **data)
        return False

    def show_badge(
        self,
        text: str,
        duration: float | None = None,
        bg: tuple[int, int, int] | None = None,
        fg: tuple[int, int, int] | None = None,
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
        sig = get_badge_signal()
        if sig.value is not None:
            sig.set(None)

    @property
    def badge_text(self) -> str | None:
        """Current badge text, or ``None`` if hidden."""
        return self._badge_text

    @property
    def badge_bg(self) -> tuple[int, int, int] | None:
        """Current badge background color, or ``None`` if hidden."""
        return self._badge_bg

    @property
    def badge_fg(self) -> tuple[int, int, int] | None:
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

    def accept(self, action, **data):
        """Forward an action to the body component."""
        accept_fn = getattr(self._body, "accept", None)
        if callable(accept_fn):
            accept_fn(action, **data)

    def resize(self, size: tuple[int, int]) -> None:
        """Resize the body and all active overlays to the new terminal size."""
        self._body.resize(size)
        self._layer_stack.resize(size)
        super().resize(size)

    def _render_surface(self, surface: Surface | _Subsurface) -> None:
        self._expire_toasts()
        self._expire_badge()
        self._body._render_surface(surface)
        self._layer_stack.render(surface)

    def _top_open_overlay(self) -> Component | None:
        for kind in (LayerKind.MODAL, LayerKind.SHEET):
            top = self._layer_stack.top(kind)
            if top is not None and getattr(top, "open", False):
                return top
        return None

    def _handle_event(self, key: str) -> None:
        result = self.try_dispatch_overlay(key)
        if result != OverlayDispatchResult.DROPPED_UNBOUND:
            self._focus_manager.sync_focus_to_overlay_or_leaf()
            return
        leaf = self._focus_manager.get_event_target()
        if leaf is not None:
            leaf._handle_event(key)
        self._focus_manager.sync_focus_to_overlay()

    def _expire_badge(self) -> None:
        if getattr(self, "_badge_until", 0) and time.monotonic() > self._badge_until:
            self.hide_badge()

    def _expire_toasts(self) -> None:
        top = self._layer_stack.top(LayerKind.TOAST)
        if top is not None and top.is_expired():
            self._pop_layer(LayerKind.TOAST)

    def show_toast(
        self,
        message: str = "",
        *,
        segments: Sequence[Segment] | None = None,
        duration: float = 2.0,
        position: ToastPosition | None = None,
    ) -> Toast:
        """Display a transient toast notification on the TOAST layer.

        Args:
            message: Toast message content (backward compat).
            segments: Optional styled segments for rich toast content.
            duration: Display duration in seconds.
            position: ToastPosition enum value (None for default TOP_RIGHT).

        Returns:
            Toast instance.
        """
        from .widgets import Toast

        existing = self._layer_stack.top(LayerKind.TOAST)
        if existing is not None:
            self._pop_layer(LayerKind.TOAST)

        if position is None:
            position = ToastPosition.TOP_RIGHT

        toast = Toast(message, segments=segments, duration=duration, position=position)
        toast.resize(self._size)
        self._layer_stack.push(LayerKind.TOAST, toast)
        return toast

    def show_sheet(self, child: Component, height: int = 8) -> Sheet:
        """Display a bottom sheet on the SHEET layer."""
        from .widgets import Sheet

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
