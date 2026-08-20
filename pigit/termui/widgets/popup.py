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
from ..feedback import FeedbackKind, style_for
from ..component import Component
from ..primitives.frame import BoxFrame
from ..mouse import MouseButton, MouseEvent, MouseKind
from .._runtime_context import get_focus_manager
from ..surface import Surface, _Subsurface
from ..primitives.text import sanitize_for_display
from ..wcwidth_table import pad_by_width, truncate_by_width
from ..types import LayerKind, OverlayDispatchResult

_logger = logging.getLogger(__name__)


class Popup(Component):
    """
    Modal shell around one inner :class:`~pigit.termui.component.Component`.

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
        """Invoke a handler from the target's resolved ``_key_handlers``.

        ``_key_handlers`` already merges ``BINDINGS`` and ``@bind_action``
        (resolved in :meth:`Component.__init__`), so both shell and child
        bindings are honoured uniformly.
        """
        fn = target._key_handlers.get(key)
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
        # x/y are 1-based (row/col), consistent with Column/Row child layout.
        self._child.x = row + 1
        self._child.y = col + 1
        self._child._size = (ow, oh)

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
        w, h = self._child._size
        sub = surface.subsurface(
            max(0, self._child.x - 1), max(0, self._child.y - 1), w, h
        )
        self._child._render_surface(sub)

    def _hit_test(self, col: int, row: int) -> tuple[Component, int, int] | None:
        """Hit-test the sole rendered child (local coords after normalization)."""
        child = self._child
        w, h = child._size
        if w <= 0 or h <= 0:
            return None
        if not (child.y <= col < child.y + w and child.x <= row < child.x + h):
            return None
        return child._hit_test(col - (child.y - 1), row - (child.x - 1))


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

    def prepare(
        self,
        message: str,
        on_result: Callable[[bool], None],
        *,
        destructive: bool = False,
    ) -> None:
        """Configure message and callback, then open the alert.

        ``destructive`` tints the border with the error-style foreground
        (irreversible confirm). Ordinary confirms stay the default border.
        """
        self._message = sanitize_for_display(message)
        self._on_result = on_result
        style = style_for(FeedbackKind.ERROR) if destructive else None
        self._frame.fg = style.fg if style is not None else palette.DEFAULT_FG
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

    def _confirm(self) -> None:
        self._shell._finish_alert(True)

    def handle_mouse(self, event: MouseEvent) -> bool:
        """Map a left click on the footer row to OK / Cancel."""
        if not self.open:
            return False
        if event.kind is not MouseKind.PRESS or event.button is not MouseButton.LEFT:
            return False
        if self._needs_rebuild:
            self._rebuild_frame()
        cr, cc, _cw, ch = self._frame.content_rect(0, 0)
        footer_row0 = cr + min(ch, len(self._content_lines)) - 1
        if event.row - 1 != footer_row0:
            return False
        footer = self._footer_text()
        col0 = event.col - 1
        ok_col = cc + footer.index("OK")
        cancel_col = cc + footer.index("Cancel")
        if ok_col <= col0 < ok_col + len("OK"):
            self._shell._finish_alert(True)
            return True
        if cancel_col <= col0 < cancel_col + len("Cancel"):
            self._shell._finish_alert(False)
            return True
        return False

    def _render_surface(self, surface: Surface | _Subsurface) -> None:
        if not self.open:
            return
        if self._needs_rebuild:
            self._rebuild_frame()
        surface.fill_rect_rgb(
            0, 0, self._outer_w, self.outer_row_count, palette.DEFAULT_BG
        )
        self._frame.draw(surface, 0, 0)
        cr, cc, cw, ch = self._frame.content_rect(0, 0)
        for i, line in enumerate(self._content_lines[:ch]):
            text = pad_by_width(truncate_by_width(line, cw), cw)
            surface.draw_text_rgb(
                cr + i,
                cc,
                text,
                fg=palette.DEFAULT_FG,
                bg=self._frame.bg,
                style_flags=self._frame.style_flags,
            )

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
        footer = self._footer_text()
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

    def _footer_text(self) -> str:
        """Return the footer label rendered on the last content line."""
        return f"[{self._confirm_key}] OK  [{self._cancel_key}] Cancel"


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

    def alert(
        self,
        message: str,
        on_result: Callable[[bool], None],
        *,
        destructive: bool = False,
    ) -> bool:
        """
        Prepare content, show this popup, and register the overlay host alert session.

        Args:
            message: Confirmation prompt.
            on_result: Callback receiving the user's True/False choice.
            destructive: If True, use the irreversible (danger) border color.

        Returns:
            True if the dialog was shown; False if another modal is already open.
        """
        if _runtime_context.is_modal_open():
            return False
        self._pane.prepare(message, on_result, destructive=destructive)
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
