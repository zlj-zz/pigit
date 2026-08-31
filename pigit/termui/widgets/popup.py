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
from ..segment import Segment
from ..surface import Surface
from ..primitives.text import sanitize_for_display
from ..theme import get_theme
from ..wcwidth_table import truncate_by_width, wcswidth
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
        dismiss_on_miss: bool = False,
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
        # When True, ComponentRoot closes this modal on a click that misses it.
        self.dismiss_on_miss = dismiss_on_miss
        self.exit_key = exit_key
        self.open = False
        self._term_size: tuple[int, int] = (80, 24)

        self.BINDINGS = [(exit_key, "_on_exit_key")]
        super().__init__(x=x, y=y, size=size)

    def get_footer_entries(self) -> list[tuple[str, str]]:
        """Footer hint for the modal dismiss key."""
        from ..keys import display_key

        return [(display_key(self.exit_key), "Close")]

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
            # Keep anchored popups on-screen; centered path above is unchanged.
            row = max(0, min(row, th - oh))
            col = max(0, min(col, tw - ow))
        # x/y are 1-based (row/col), consistent with Column/Row child layout.
        self._child.x = row + 1
        self._child.y = col + 1
        self._child._size = (ow, oh)

    def _on_exit_key(self) -> None:
        self.end_session()
        self.hide()

    def paint(self, surface: Surface) -> None:
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
        self._child.paint(sub)

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
        self._kind: FeedbackKind | None = None
        self._content_rows: list[list[Segment]] = []
        self._needs_rebuild = True
        theme = get_theme()
        self._frame = BoxFrame(
            0, 0, title="Confirm", fg=theme.fg_primary, bg=theme.bg_chrome
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
        kind: FeedbackKind | None = None,
    ) -> None:
        """Configure message, semantic kind, and callback, then open the alert.

        ``kind`` colors the border and OK action (``ERROR`` for irreversible
        confirms). ``None`` keeps the neutral chrome.
        """
        self._message = sanitize_for_display(message)
        self._on_result = on_result
        self._kind = kind
        self._apply_chrome()
        self.open_alert()
        self._needs_rebuild = True

    def _apply_chrome(self) -> None:
        """Set border/title colors from theme and optional feedback kind."""
        theme = get_theme()
        self._frame.title = "Confirm"
        self._frame.bg = theme.bg_chrome
        style = style_for(self._kind)
        if style is not None:
            self._frame.fg = style.fg
            self._frame.style_flags = style.style_flags
        else:
            self._frame.fg = theme.fg_primary
            self._frame.style_flags = 0

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
        self._content_rows = self._build_content_rows()
        self._frame.set_inner_size(self._inner_w, len(self._content_rows))
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
        footer_row0 = cr + min(ch, len(self._content_rows)) - 1
        if event.row - 1 != footer_row0:
            return False
        footer = self._footer_plain()
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

    def paint(self, surface: Surface) -> None:
        if not self.open:
            return
        if self._needs_rebuild:
            self._rebuild_frame()
        theme = get_theme()
        surface.fill_rect_rgb(
            0, 0, self._outer_w, self.outer_row_count, theme.bg_chrome
        )
        self._frame.draw(surface, 0, 0)
        cr, cc, cw, ch = self._frame.content_rect(0, 0)
        for i, row in enumerate(self._content_rows[:ch]):
            surface.draw_segments(cr + i, cc, row)
            used = sum(max(0, wcswidth(seg.text)) for seg in row)
            if used < cw:
                surface.draw_text_rgb(
                    cr + i,
                    cc + used,
                    " " * (cw - used),
                    fg=theme.fg_primary,
                    bg=theme.bg_chrome,
                )

    def _build_content_rows(self) -> list[list[Segment]]:
        """Build message and footer rows as styled segments.

        Lines are wrapped and padded by *display width* (``wcswidth``), so a
        line containing full-width CJK characters can never exceed ``inner``
        cells and paint over the frame border.
        """
        theme = get_theme()
        inner = self._inner_w
        body = sanitize_for_display(self._message)
        wrapped: list[str] = []
        for raw in body.splitlines() or [body]:
            chunk = raw
            while wcswidth(chunk) > inner:
                take = 0
                width = 0
                for ch in chunk:
                    w = wcswidth(ch)
                    if width + w > inner:
                        break
                    width += w
                    take += 1
                if take == 0:
                    take = 1  # a single wide char alone exceeds inner
                wrapped.append(chunk[:take])
                chunk = chunk[take:]
            if chunk:
                wrapped.append(chunk)
        if not wrapped:
            wrapped = [""]

        rows: list[list[Segment]] = []
        for line in wrapped:
            rows.append(
                [
                    Segment(
                        self._pad_cells(line, inner),
                        fg=theme.fg_primary,
                        bg=theme.bg_chrome,
                    )
                ]
            )
        rows.append([Segment(" " * inner, fg=theme.fg_primary, bg=theme.bg_chrome)])
        footer = self._footer_segments()
        plain = "".join(seg.text for seg in footer)
        if wcswidth(plain) > inner:
            # Keep hit-testing stable: prefer a single clipped footer row.
            rows.append(
                [
                    Segment(
                        self._pad_cells(truncate_by_width(plain, inner), inner),
                        fg=theme.fg_muted,
                        bg=theme.bg_chrome,
                    )
                ]
            )
        else:
            pad = inner - wcswidth(plain)
            if pad:
                footer = footer + [
                    Segment(" " * pad, fg=theme.fg_muted, bg=theme.bg_chrome)
                ]
            rows.append(footer)
        return rows

    @staticmethod
    def _pad_cells(text: str, width: int) -> str:
        """Pad *text* (display width ≤ *width*) to exactly ``width`` cells."""
        return text + " " * max(0, width - wcswidth(text))

    def _footer_plain(self) -> str:
        """Return the footer as plain text for mouse hit-testing."""
        return "".join(seg.text for seg in self._footer_segments())

    def _footer_segments(self) -> list[Segment]:
        """Return styled OK / Cancel footer segments."""
        theme = get_theme()
        confirm = keys.display_key(self._confirm_key)
        cancel = keys.display_key(self._cancel_key)
        ok_fg = (
            theme.fg_danger if self._kind is FeedbackKind.ERROR else theme.fg_primary
        )
        return [
            Segment("[", fg=theme.fg_muted, bg=theme.bg_chrome),
            Segment(confirm, fg=theme.fg_muted, bg=theme.bg_chrome),
            Segment("] ", fg=theme.fg_muted, bg=theme.bg_chrome),
            Segment(
                "OK",
                fg=ok_fg,
                bg=theme.bg_chrome,
                style_flags=palette.STYLE_BOLD,
            ),
            Segment("  [", fg=theme.fg_muted, bg=theme.bg_chrome),
            Segment(cancel, fg=theme.fg_muted, bg=theme.bg_chrome),
            Segment("] ", fg=theme.fg_muted, bg=theme.bg_chrome),
            Segment("Cancel", fg=theme.fg_muted, bg=theme.bg_chrome),
        ]


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
        kind: FeedbackKind | None = None,
    ) -> bool:
        """
        Prepare content, show this popup, and register the overlay host alert session.

        Args:
            message: Confirmation prompt.
            on_result: Callback receiving the user's True/False choice.
            kind: Semantic feedback kind for chrome / OK styling.
                Use ``FeedbackKind.ERROR`` for irreversible confirms.

        Returns:
            True if the dialog was shown; False if another modal is already open.
        """
        if _runtime_context.is_modal_open():
            return False
        self._pane.prepare(message, on_result, kind=kind)
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
