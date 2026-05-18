"""
Module: pigit/termui/widgets/popup.py
Description: Popup shell, AlertDialog and AlertDialogBody.
Author: Zev
Date: 2026-05-18
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from .. import _runtime_context, keys, palette
from .._bindings import resolve_key_handlers_merged
from .._component import Component
from .._frame import BoxFrame
from .._runtime_context import get_focus_manager
from .._surface import Surface, _Subsurface
from .._text import sanitize_for_display
from ..types import LayerKind, OverlayDispatchResult

_logger = logging.getLogger(__name__)


class Popup(Component):
    """
    Modal shell around one inner :class:`~pigit.termui._component.Component`.

    :meth:`toggle` and ``exit_key`` coordinate modal session lifecycle through
    the runtime context (push/pop on the ``MODAL`` layer).
    """

    def __init__(
        self,
        child: Component,
        *,
        offset: tuple[int, int] | None = None,
        exit_key: str = keys.KEY_ESC,
        x: int = 1,
        y: int = 1,
        size: tuple[int, int] | None = None,
    ) -> None:
        self._child = child
        set_on_toggle = getattr(child, "set_on_toggle", None)
        if callable(set_on_toggle):
            set_on_toggle(self.toggle)
        self._offset = offset
        self.exit_key = exit_key
        self.open = False
        self._term_size: tuple[int, int] = (80, 24)

        self.BINDINGS = [(exit_key, "_on_exit_key")]
        super().__init__(x=x, y=y, size=size)
        self._resolved_handlers = resolve_key_handlers_merged(
            self, type(self), getattr(self, "BINDINGS", None)
        )
        self._resolved_child_handlers = resolve_key_handlers_merged(
            self._child, type(self._child), getattr(self._child, "BINDINGS", None)
        )

    def dispatch_overlay_key(self, key: str) -> OverlayDispatchResult:
        """
        Handle one key while this shell is the active modal: try shell bindings,
        then the child's, then fallback.
        """
        if self._invoke_binding_target(self, key):
            return OverlayDispatchResult.HANDLED_EXPLICIT
        if self._invoke_binding_target(self._child, key):
            return OverlayDispatchResult.HANDLED_EXPLICIT
        return self._fallback_overlay_key(key)

    def _invoke_binding_target(self, target: Component, key: str) -> bool:
        if target is self:
            handlers = self._resolved_handlers
        elif target is self._child:
            handlers = self._resolved_child_handlers
        else:
            handlers = resolve_key_handlers_merged(
                target,
                type(target),
                getattr(target, "BINDINGS", None),
            )
        fn = handlers.get(key)
        if fn is None:
            return False
        fn()
        return True

    def _fallback_overlay_key(self, key: str) -> OverlayDispatchResult:
        """After shell and child miss: swallow unbound keys."""
        return OverlayDispatchResult.DROPPED_UNBOUND

    def begin_session(self) -> None:
        """Push this popup onto the MODAL layer via the runtime context."""
        _runtime_context.layer_push(LayerKind.MODAL, self)
        fm = get_focus_manager()
        if fm is not None:
            fm.set_focus_chain(self)

    def end_session(self) -> None:
        """Pop the top component from the MODAL layer via the runtime context."""
        _runtime_context.layer_pop(LayerKind.MODAL)

    def toggle(self) -> None:
        """Toggle the popup session via the runtime context."""
        host = _runtime_context.get_overlay_host()
        if host is None:
            return
        top = host._layer_stack.top(LayerKind.MODAL)
        if top is self:
            host._layer_stack.pop(LayerKind.MODAL)
            self.hide()
            return
        if top is not None:
            return
        before_show = getattr(self._child, "on_before_show", None)
        if callable(before_show):
            before_show()
        self.show()
        host._layer_stack.push(LayerKind.MODAL, self)
        fm = get_focus_manager()
        if fm is not None:
            fm.set_focus_chain(self)

    def show(self) -> None:
        """Open the popup."""
        self.open = True

    def hide(self) -> None:
        """Close the popup."""
        self.open = False

    def resize(self, size: tuple[int, int]) -> None:
        """Resize the popup and its child to the given terminal size."""
        self._term_size = (int(size[0]), int(size[1]))
        self._child.resize(size)
        self._layout_content()
        self.refresh()

    def relayout_content(self) -> None:
        """Recompute child ``x`` / ``y`` / ``_size`` after child geometry changes."""
        self._layout_content()

    def _layout_content(self) -> None:
        if not hasattr(self._child, "_outer_w"):
            return
        if getattr(self._child, "_needs_rebuild", False):
            rebuild = getattr(self._child, "_rebuild_frame", None)
            if rebuild is not None:
                rebuild()
        tw, th = self._term_size
        ow = getattr(self._child, "_outer_w", 0)
        oh = getattr(self._child, "outer_row_count", 0)
        if self._offset is None:
            row = max(0, (th - oh) // 2)
            col = max(0, (tw - ow) // 2)
        else:
            row, col = int(self._offset[0]), int(self._offset[1])
        self._child.x = row
        self._child.y = col
        self._child._size = (ow, oh)

    def refresh(self) -> None:
        """No-op refresh for compatibility."""

    def _on_exit_key(self) -> None:
        self.end_session()
        self.hide()

    def _render_surface(self, surface: Surface | _Subsurface) -> None:
        if not self.open:
            return
        curr_size = (surface.width, surface.height)
        if self._term_size != curr_size or self._child._size == (0, 0):
            self.resize(curr_size)
        self._layout_content()
        self._child._render_surface(surface)


class AlertDialogBody(Component):
    """
    Inner bordered confirmation content; shell is :class:`AlertDialog`.

    ESC is handled by the :class:`Popup` shell.
    """

    def __init__(
        self,
        shell: AlertDialog,
        x: int = 1,
        y: int = 1,
        size: tuple[int, int] | None = None,
        message: str = "",
        on_result: Callable[[bool], None] | None = None,
        inner_width: int | None = None,
        confirm_key: str = keys.KEY_ENTER,
        cancel_key: str = keys.KEY_ESC,
    ) -> None:
        if on_result is None:
            raise ValueError("AlertDialog requires on_result in MVP.")
        self._shell = shell
        self._on_result = on_result
        self._message = sanitize_for_display(message)
        self._inner_w_cfg = inner_width
        self._confirm_key = confirm_key
        self._cancel_key = cancel_key
        self.open = False
        self._term_cols = 80
        self._term_lines = 24
        self._inner_w = 40
        self._outer_w = 42
        self.outer_row_count = 8
        self._content_lines: list[str] = []
        self._needs_rebuild = True
        self._frame = BoxFrame(
            0, 0, title="Alert", fg=palette.DEFAULT_FG, bg=palette.DEFAULT_BG
        )
        self.BINDINGS = [(self._confirm_key, "_confirm")]
        super().__init__(x=x, y=y, size=size)

    def open_alert(self) -> None:
        """Open the alert dialog body."""
        if self.open:
            return
        self.open = True

    def prepare(self, message: str, on_result: Callable[[bool], None]) -> None:
        """Configure message and callback, then open the alert."""
        self._message = sanitize_for_display(message)
        self._on_result = on_result
        self.open_alert()
        self._needs_rebuild = True

    def reset_state(self) -> None:
        """Close the alert dialog body."""
        self.open = False

    def resize(self, size: tuple[int, int]) -> None:
        """Resize the alert body and mark it for rebuild."""
        self._term_cols = int(size[0])
        self._term_lines = int(size[1])
        self._needs_rebuild = True
        super().resize(size)

    def _rebuild_frame(self) -> None:
        inner_w = (
            self._inner_w_cfg
            if self._inner_w_cfg is not None
            else max(20, self._term_cols // 2)
        )
        inner_w = max(16, min(inner_w, self._term_cols - 4))
        self._inner_w = inner_w
        self._content_lines = self._build_content_lines()
        self._frame.set_inner_size(self._inner_w, len(self._content_lines))
        self._outer_w = self._frame.outer_width
        self.outer_row_count = self._frame.outer_height
        self._needs_rebuild = False

    def refresh(self) -> None:
        """No-op refresh for compatibility."""

    def _confirm(self) -> None:
        self._shell._finish_alert(True)

    def _render_surface(self, surface: Surface | _Subsurface) -> None:
        if not self.open:
            return
        if self._needs_rebuild:
            self._rebuild_frame()
        surface.fill_rect_rgb(
            self.x, self.y, self._outer_w, self.outer_row_count, palette.DEFAULT_BG
        )
        self._frame.draw_onto(surface, self.x, self.y)
        self._frame.draw_content(surface, self.x, self.y, self._content_lines)

    def _build_content_lines(self) -> list[str]:
        inner = self._inner_w
        body = sanitize_for_display(self._message)
        wrapped: list[str] = []
        for raw in body.splitlines() or [body]:
            seg = raw
            while seg:
                wrapped.append(seg[:inner])
                seg = seg[inner:]
        if not wrapped:
            wrapped = [""]
        footer = f"[{self._confirm_key}] OK  [{self._cancel_key}] Cancel"
        footer_lines: list[str] = []
        rest = footer
        while rest:
            footer_lines.append(rest[:inner])
            rest = rest[inner:]
        lines: list[str] = []
        for line in wrapped:
            lines.append(line[:inner].ljust(inner))
        lines.append(" " * inner)
        for fl in footer_lines:
            lines.append(fl[:inner].ljust(inner))
        return lines


class AlertDialog(Popup):
    """
    Confirmation UI as a :class:`Popup` shell around :class:`AlertDialogBody`.

    Call :meth:`alert` from application code with a message and ``on_result`` callback.
    """

    def __init__(
        self,
        x: int = 1,
        y: int = 1,
        size: tuple[int, int] | None = None,
        inner_width: int | None = None,
        on_result: Callable[[bool], None] | None = None,
        confirm_key: str = keys.KEY_ENTER,
        cancel_key: str = keys.KEY_ESC,
    ) -> None:
        if on_result is None:
            raise ValueError("AlertDialog requires on_result in MVP.")
        self._pane = AlertDialogBody(
            self,
            x=x,
            y=y,
            size=size,
            on_result=on_result,
            inner_width=inner_width,
            confirm_key=confirm_key,
            cancel_key=cancel_key,
        )
        super().__init__(
            self._pane,
            offset=None,
            exit_key=keys.KEY_ESC,
            x=x,
            y=y,
            size=size,
        )

    def _on_exit_key(self) -> None:
        self._finish_alert(False)

    def alert(self, message: str, on_result: Callable[[bool], None]) -> bool:
        """
        Prepare content, show this popup, and register the overlay host alert session.

        Returns:
            True if the dialog was shown; False if another modal is already open.
        """
        if _runtime_context.is_modal_open():
            return False
        self._pane.prepare(message, on_result)
        self.relayout_content()
        self.show()
        self.begin_session()
        return True

    def _finish_alert(self, value: bool) -> None:
        fn = self._pane._on_result
        self.end_session()
        self.hide()
        self._pane.reset_state()
        if fn is None:
            return
        try:
            fn(value)
        except Exception:
            _logger.exception("AlertDialog on_result failed")

    def reset_state(self) -> None:
        """Clear body state and hide the shell (e.g. after host error recovery)."""
        self.hide()
        self._pane.reset_state()

    def resize(self, size: tuple[int, int]) -> None:
        """Resize the alert dialog and its child pane."""
        super().resize(size)
