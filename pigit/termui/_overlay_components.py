# -*- coding: utf-8 -*-
"""
Module: pigit/termui/_overlay_components.py
Description: Overlay components including HelpPanel, Popup, AlertDialog, Toast, and Sheet.
Author: Zev
Date: 2026-04-19
"""

from __future__ import annotations

import logging
import time
from typing import Any, Callable, ClassVar, Optional, Sequence

from ._bindings import resolve_key_handlers_merged
from ._component_base import Component
from ._frame import BoxFrame
from ._segment import Segment
from ._text import sanitize_for_display
from ._layout import Padding
from ._surface import Surface
from .palette import DEFAULT_BG, DEFAULT_FG
from .wcwidth_table import truncate_by_width, wcswidth
from .types import ToastPosition, OverlayDispatchResult, LayerKind
from . import keys
from . import _overlay_context

_logger = logging.getLogger(__name__)

# Maximum number of lines to display in a Toast (safety limit)
MAX_TOAST_LINES = 100

HelpEntry = tuple[str, str]


class HelpPanel(Component):
    """
    Plain help content (bordered, scrollable key list). Not modal until wrapped.

    Wrap with :class:`Popup` to make it modal; :class:`Popup` uses
    :mod:`~pigit.termui._overlay_context` to manage the modal layer lifecycle.
    Bind ``?`` to a handler that refreshes rows (e.g. :meth:`refresh_entries_from_source`)
    when opening help, then calls ``popup.toggle()``.

    :data:`TOGGLE_HELP_SEMANTIC_KEYS` lists keys that toggle help while this panel's
    wrapping :class:`Popup` is active; overlay routing calls
    :meth:`Popup.dispatch_overlay_key`, which runs :meth:`Popup.toggle` for those keys
    when shell and child bindings do not handle them.
    """

    TOGGLE_HELP_SEMANTIC_KEYS: ClassVar[tuple[str, ...]] = ("?",)

    BINDINGS = [
        (keys.KEY_DOWN, "scroll_down"),
        (keys.KEY_UP, "scroll_up"),
        ("j", "scroll_down"),
        ("k", "scroll_up"),
    ]

    def __init__(
        self,
        inner_width: Optional[int] = None,
        inner_height: Optional[int] = None,
        x: int = 1,
        y: int = 1,
        size: Optional[tuple[int, int]] = None,
        *,
        entries_source: Optional[Component] = None,
        key_fg: Optional[tuple[int, int, int]] = None,
    ) -> None:
        super().__init__(x=x, y=y, size=size)
        self._inner_w_cfg = inner_width
        self._inner_h_cfg = inner_height
        self._entries_source = entries_source
        self._key_fg = key_fg
        self._lines: list[str] = []
        self._offset = 0
        self._inner_w = 40
        self._scroll_h = 6
        self._outer_w = 42
        self.outer_row_count = 10
        self._frame = BoxFrame(
            0, 0, title="Help   esc close", fg=DEFAULT_FG, bg=DEFAULT_BG
        )
        self._padding = Padding(top=2, right=4, bottom=2, left=4)
        # Each element is a list of Segment for one line.
        self._line_segments: list[list[Segment]] = []

    def resize(self, size: tuple[int, int]) -> None:
        """Recalculate inner and outer dimensions for the given terminal size."""
        tw, th = int(size[0]), int(size[1])
        avail_w, avail_h = self._padding.apply((tw, th))
        inner_w = (
            self._inner_w_cfg if self._inner_w_cfg is not None else max(24, tw // 2)
        )
        inner_h = (
            self._inner_h_cfg if self._inner_h_cfg is not None else max(8, th // 2)
        )
        inner_w = max(16, min(inner_w, avail_w))
        inner_h = max(5, min(inner_h, avail_h))
        self._inner_w = inner_w
        self._scroll_h = max(1, inner_h - 1)
        self._frame.set_inner_size(self._inner_w, self._scroll_h)
        self._outer_w = self._frame.outer_width
        self.outer_row_count = self._frame.outer_height
        super().resize(size)

    def set_entries(self, entries: list[HelpEntry]) -> None:
        """Set flat help entries and rebuild rendered lines."""
        if not entries:
            self._lines = []
            self._line_segments = []
            self._offset = 0
            return
        max_key_w = max(wcswidth(key_disp) for key_disp, _ in entries)
        lines: list[str] = []
        segments: list[list[Segment]] = []
        for key_disp, desc in entries:
            pad = max_key_w - wcswidth(key_disp)
            line = f"{key_disp}{' ' * pad}  {desc}"
            lines.append(line)
            seg: list[Segment] = []
            if self._key_fg is not None:
                seg.append(Segment(key_disp, fg=self._key_fg))
                seg.append(Segment(" " * pad + "  "))
            else:
                seg.append(Segment(key_disp + " " * pad + "  "))
            seg.append(Segment(desc))
            segments.append(seg)
        self._lines = lines
        self._line_segments = segments
        self._offset = 0

    def set_grouped_entries(self, groups: list[tuple[str, list[HelpEntry]]]) -> None:
        """Set grouped help entries with category headers and rebuild rendered lines."""
        from .palette import STYLE_BOLD

        if not groups:
            self._lines = []
            self._line_segments = []
            self._offset = 0
            return
        max_key_w = 0
        for _, entries in groups:
            for key_disp, _ in entries:
                max_key_w = max(max_key_w, wcswidth(key_disp))

        lines: list[str] = []
        segments: list[list[Segment]] = []
        for title, entries in groups:
            if not entries:
                continue
            # Category header
            lines.append(title)
            segments.append([Segment(title, style_flags=STYLE_BOLD)])
            # Indented entries
            for key_disp, desc in entries:
                pad = max_key_w - wcswidth(key_disp)
                line = f"  {key_disp}{' ' * pad}  {desc}"
                lines.append(line)
                seg: list[Segment] = []
                seg.append(Segment("  "))
                if self._key_fg is not None:
                    seg.append(Segment(key_disp, fg=self._key_fg))
                    seg.append(Segment(" " * pad + "  "))
                else:
                    seg.append(Segment(key_disp + " " * pad + "  "))
                seg.append(Segment(desc))
                segments.append(seg)
            # Blank line between groups
            lines.append("")
            segments.append([])

        self._lines = lines
        self._line_segments = segments
        self._offset = 0

    def on_before_show(self) -> None:
        """Refresh help entries from the configured source before opening."""
        if self._entries_source is not None:
            self.refresh_entries_from_source(self._entries_source)

    def refresh_entries_from_source(
        self, entries_source: Any, *, max_rows: int = 256
    ) -> None:
        """
        Build grouped help rows from ``entries_source.children``: collect
        :meth:`~pigit.termui.components.Component.get_help_entries` from each mapped child,
        group by :meth:`~pigit.termui.components.Component.get_help_title`, then
        :meth:`set_grouped_entries` (truncated to ``max_rows``).

        This is independent of how or when the panel is shown; call it from app code when
        you want the list to reflect the current tree (e.g. before opening help).
        """

        children = getattr(entries_source, "children", None)
        if children is None:
            raise TypeError(
                "Source must expose a non-optional `children` sequence (e.g. TabView, Column)."
            )
        groups: list[tuple[str, list[HelpEntry]]] = []
        for panel in children:
            entries = panel.get_help_entries()
            if not entries:
                continue
            title_getter = getattr(panel, "get_help_title", None)
            if callable(title_getter):
                title = title_getter()
            else:
                title = panel.__class__.__name__.replace("Panel", "")
            groups.append((title, entries))
        self.set_grouped_entries(groups)

    def scroll_down(self) -> None:
        """Scroll the help content down by one line."""
        max_off = max(0, len(self._lines) - self._scroll_h)
        self._offset = min(self._offset + 1, max_off)

    def scroll_up(self) -> None:
        """Scroll the help content up by one line."""
        self._offset = max(0, self._offset - 1)

    def refresh(self) -> None:
        """No-op refresh for compatibility."""
        pass

    def _render_surface(self, surface: Surface) -> None:
        # Fill the entire panel area with default background to prevent
        # underlying panel content from leaking through.
        surface.fill_rect_rgb(
            self.x, self.y, self._outer_w, self.outer_row_count, DEFAULT_BG
        )
        self._frame.draw_onto(surface, self.x, self.y)

        content_row = self.x + 1
        content_col = self.y + 1
        chunk = self._line_segments[self._offset : self._offset + self._scroll_h]
        for i, segments in enumerate(chunk):
            row = content_row + i
            x = content_col
            for seg in segments:
                text = seg.text
                text_w = wcswidth(text)
                avail = content_col + self._inner_w - x
                if text_w > avail:
                    text = truncate_by_width(text, avail)
                surface.draw_text_rgb(
                    row,
                    x,
                    text,
                    fg=seg.fg,
                    bg=seg.bg,
                    style_flags=seg.style_flags,
                )
                x += wcswidth(text)
            # Pad remaining width with spaces to prevent residue
            if x < content_col + self._inner_w:
                surface.fill_rect_rgb(
                    row, x, content_col + self._inner_w - x, 1, DEFAULT_BG
                )


class Popup(Component):
    """
    Modal shell around one inner :class:`~pigit.termui.components.Component`.

    :meth:`toggle` and ``exit_key`` coordinate modal session lifecycle through
    :mod:`~pigit.termui._overlay_context` (push/pop on the ``MODAL`` layer).

    Wrapped content may declare :data:`TOGGLE_HELP_SEMANTIC_KEYS` so
    :meth:`_fallback_overlay_key` calls :meth:`toggle` for those keys.
    """

    def __init__(
        self,
        child: Component,
        *,
        offset: Optional[tuple[int, int]] = None,
        exit_key: str = keys.KEY_ESC,
        x: int = 1,
        y: int = 1,
        size: Optional[tuple[int, int]] = None,
    ) -> None:
        self._child = child
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
        Handle one key while this shell is the active modal: try shell bindings, then
        the child's, then :meth:`_fallback_overlay_key` (e.g. help ``?`` or swallow).
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
        """
        After shell and child miss: if the wrapped component defines semantic toggle keys,
        call :meth:`toggle`; otherwise swallow.
        """

        toggle_keys = getattr(type(self._child), "TOGGLE_HELP_SEMANTIC_KEYS", ())
        if key in toggle_keys:
            self.toggle()
            return OverlayDispatchResult.HANDLED_IMPLICIT
        return OverlayDispatchResult.DROPPED_UNBOUND

    def begin_session(self) -> None:
        """Push this popup onto the MODAL layer via overlay_context."""
        _overlay_context.layer_push(LayerKind.MODAL, self)

    def end_session(self) -> None:
        """Pop the top component from the MODAL layer via overlay_context."""
        _overlay_context.layer_pop(LayerKind.MODAL)

    def toggle(self) -> None:
        """Toggle the popup session via overlay_context."""
        host = _overlay_context.get_overlay_host()
        if host is None:
            return
        top = host._layer_stack.top(LayerKind.MODAL)
        if top is self:
            host._layer_stack.pop(LayerKind.MODAL)
            self.hide()
            return
        if top is not None:
            # Another modal is active; do not steal focus.
            return
        before_show = getattr(self._child, "on_before_show", None)
        if callable(before_show):
            before_show()
        self.show()
        host._layer_stack.push(LayerKind.MODAL, self)

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
        # Ensure the child's geometry is current before reading it.
        if getattr(self._child, "_needs_rebuild", False):
            rebuild = getattr(self._child, "_rebuild_frame", None)
            if rebuild is not None:
                rebuild()
        tw, th = self._term_size
        ow = self._child._outer_w
        oh = self._child.outer_row_count
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
        pass

    def _on_exit_key(self) -> None:
        self.end_session()
        self.hide()

    def _render_surface(self, surface: Surface) -> None:
        if not self.open:
            return
        # Ensure the popup and its child are sized for the current surface before
        # laying out content. Side-attached popups (e.g. HelpPanel) may never have
        # been resized because they are not in the component tree.
        curr_size = (surface.width, surface.height)
        if self._term_size != curr_size or self._child._size == (0, 0):
            self.resize(curr_size)
        self._layout_content()
        self._child._render_surface(surface)


class AlertDialogBody(Component):
    """
    Inner bordered confirmation content; shell is :class:`AlertDialog` (:class:`Popup`).

    ESC is handled by the :class:`Popup` shell (see :meth:`AlertDialog._on_exit_key`).
    """

    def __init__(
        self,
        shell: "AlertDialog",
        x: int = 1,
        y: int = 1,
        size: Optional[tuple[int, int]] = None,
        message: str = "",
        on_result: Optional[Callable[[bool], None]] = None,
        inner_width: Optional[int] = None,
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
        self._frame = BoxFrame(0, 0, title="Alert", fg=DEFAULT_FG, bg=DEFAULT_BG)
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
        pass

    def _confirm(self) -> None:
        self._shell._finish_alert(True)

    def _render_surface(self, surface: Surface) -> None:
        if not self.open:
            return
        if self._needs_rebuild:
            self._rebuild_frame()
        # Fill the entire dialog area with default background to prevent
        # previous frame content from leaking through the borders.
        surface.fill_rect_rgb(
            self.x, self.y, self._outer_w, self.outer_row_count, DEFAULT_BG
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
    Opening uses :meth:`~pigit.termui.components_overlay.Popup.show` and
    :meth:`~pigit.termui.components_overlay.Popup.begin_session` through
    :mod:`~pigit.termui._overlay_context`; closing uses
    :meth:`~pigit.termui.components_overlay.Popup.end_session` and
    :meth:`~pigit.termui.components_overlay.Popup.hide`.

    Panels typically set ``_alert_dialog`` and ``_alert_popup`` to this same instance.
    """

    def __init__(
        self,
        x: int = 1,
        y: int = 1,
        size: Optional[tuple[int, int]] = None,
        inner_width: Optional[int] = None,
        on_result: Optional[Callable[[bool], None]] = None,
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

        if _overlay_context.is_modal_open():
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


class Toast(Component):
    """Auto-dismissing notification message (TOAST layer) with border, animation, and configurable position."""

    def __init__(
        self,
        message: str = "",
        *,
        segments: Optional[Sequence[Segment]] = None,
        duration: float = 2.0,
        size: Optional[tuple[int, int]] = None,
        clock: Callable[[], float] = time.monotonic,
        position: ToastPosition = ToastPosition.TOP_RIGHT,
        enter_duration: float = 0.5,
        exit_duration: float = 0.5,
    ) -> None:
        super().__init__(size=size)
        self._segments: list[Segment] = (
            list(segments) if segments else [Segment(message)]
        )
        self.duration = duration
        self._clock = clock
        self._position = position

        if enter_duration + exit_duration > duration:
            enter_duration = 0.0
            exit_duration = 0.0
        self._enter_duration = enter_duration
        self._exit_duration = exit_duration

        self._created_at = self._clock()
        self.open = True

        self._term_size: tuple[int, int] = (0, 0)
        self._needs_rebuild = True
        self._frame: Optional[BoxFrame] = None
        self._lines: list[str] = []
        self._outer_w = 0
        self.outer_row_count = 0

    def is_expired(self) -> bool:
        """Return True if the toast has exceeded its display duration."""
        return self._clock() - self._created_at > self.duration + self._exit_duration

    def resize(self, size: tuple[int, int]) -> None:
        """Resize the toast and mark it for rebuild if the size changed."""
        new_size = (int(size[0]), int(size[1]))
        if self._term_size != new_size:
            self._term_size = new_size
            self._needs_rebuild = True
        super().resize(size)

    def _rebuild_frame(self) -> None:
        """Rebuild BoxFrame and content lines based on current terminal size."""
        max_inner_w = max(0, self._term_size[0] - 4)
        # Split segments into lines by \n
        line_segments: list[list[Segment]] = [[]]
        for seg in self._segments:
            parts = seg.text.split("\n")
            for i, part in enumerate(parts):
                if i > 0:
                    line_segments.append([])
                if part:
                    line_segments[-1].append(
                        Segment(part, fg=seg.fg, bg=seg.bg, style_flags=seg.style_flags)
                    )
        # Truncate each line to max_inner_w and compute inner width
        truncated: list[list[Segment]] = []
        inner_w = 0
        for line in line_segments[:MAX_TOAST_LINES]:
            line_w = 0
            new_line: list[Segment] = []
            for seg in line:
                seg_w = wcswidth(seg.text)
                if line_w + seg_w > max_inner_w:
                    # Truncate this segment to fit
                    avail = max(0, max_inner_w - line_w)
                    if avail > 0:
                        truncated_text = truncate_by_width(seg.text, avail)
                        new_line.append(
                            Segment(
                                truncated_text,
                                fg=seg.fg,
                                bg=seg.bg,
                                style_flags=seg.style_flags,
                            )
                        )
                        line_w += wcswidth(truncated_text)
                    break
                new_line.append(seg)
                line_w += seg_w
            truncated.append(new_line)
            inner_w = max(inner_w, line_w)

        self._line_segments = truncated
        inner_h = len(self._line_segments)

        if self._frame is None:
            self._frame = BoxFrame(inner_w, inner_h, fg=DEFAULT_FG, bg=DEFAULT_BG)
        else:
            self._frame.set_inner_size(inner_w, inner_h)
        self._outer_w = self._frame.outer_width
        self.outer_row_count = self._frame.outer_height
        self._needs_rebuild = False

    def _compute_slide_offset(self, elapsed: float) -> int:
        """Compute horizontal animation offset.

        Args:
            elapsed: Seconds elapsed since creation.

        Returns:
            Column offset relative to the target position (target is 0).
            LEFT_*: negative means left of target (off-screen)
            RIGHT_*: positive means right of target (off-screen)
        """
        total = self.duration
        enter = self._enter_duration
        exit = self._exit_duration
        dist = self._outer_w if self._outer_w > 0 else 1

        is_left = self._position in (ToastPosition.TOP_LEFT, ToastPosition.BOTTOM_LEFT)
        direction = -1 if is_left else 1

        if enter == 0 and exit == 0:
            return 0

        if elapsed < enter and enter > 0:
            progress = elapsed / enter
            return direction * int(dist * (1.0 - progress))
        if elapsed > total - exit and exit > 0:
            progress = max(0.0, (total - elapsed) / exit)
            return direction * int(dist * (1.0 - progress))
        return 0

    def _compute_base_position(self, surface) -> tuple[int, int]:
        """Compute the target (row, col) without animation offset."""
        if self._position in (ToastPosition.TOP_LEFT, ToastPosition.TOP_RIGHT):
            base_row = 1
        else:
            base_row = max(0, surface.height - self.outer_row_count - 1)

        if self._position in (ToastPosition.TOP_LEFT, ToastPosition.BOTTOM_LEFT):
            base_col = 1
        else:
            base_col = max(0, surface.width - self._outer_w - 1)

        return base_row, base_col

    def dispatch_overlay_key(self, key: str) -> OverlayDispatchResult:
        """Drop all keys; toasts are non-interactive."""
        return OverlayDispatchResult.DROPPED_UNBOUND

    def _render_surface(self, surface: Surface) -> None:
        if not self.open:
            return

        if surface.width < 4 or surface.height < 3:
            return

        if self._needs_rebuild:
            self._rebuild_frame()

        if self._frame is None:
            return

        elapsed = self._clock() - self._created_at
        offset_x = self._compute_slide_offset(elapsed)
        base_row, base_col = self._compute_base_position(surface)
        render_col = base_col + offset_x

        if base_row + self.outer_row_count <= 0 or base_row >= surface.height:
            return
        if render_col + self._outer_w <= 0 or render_col >= surface.width:
            return

        # Clear background to prevent residue from previous frames or underlying content.
        surface.fill_rect_rgb(
            base_row, render_col, self._outer_w, self.outer_row_count, DEFAULT_BG
        )
        self._frame.draw_onto(surface, base_row, render_col)
        # Draw content lines using segments
        content_row = base_row + 1
        content_col = render_col + 1
        for i, segments in enumerate(self._line_segments):
            row = content_row + i
            if row >= surface.height:
                break
            surface.draw_segments(row, content_col, segments)
            # Pad remaining width to prevent residue
            line_text = "".join(s.text for s in segments)
            line_w = wcswidth(line_text)
            pad_col = content_col + line_w
            pad_w = content_col + self._frame.inner_width - pad_col
            if pad_w > 0:
                surface.fill_rect_rgb(row, pad_col, pad_w, 1, DEFAULT_BG)

    @property
    def message(self) -> str:
        """Toast message content (backward compatibility)."""
        return "".join(s.text for s in self._segments)

    def hide(self) -> None:
        """Close the toast."""
        self.open = False

    def refresh(self) -> None:
        """No-op refresh for compatibility."""
        pass


class Sheet(Component):
    """Bottom sheet panel, similar to mobile bottom sheet (SHEET layer)."""

    def __init__(
        self,
        child: Component,
        height: int = 8,
        size: Optional[tuple[int, int]] = None,
    ) -> None:
        super().__init__(size=size)
        self._child = child
        child.parent = self
        self._target_height = height
        self._child_dispatch = getattr(child, "dispatch_overlay_key", None)
        self.open = True

    def dispatch_overlay_key(self, key: str) -> OverlayDispatchResult:
        """Forward overlay keys to the child component if supported."""
        if self._child_dispatch is not None:
            return self._child_dispatch(key)
        return OverlayDispatchResult.DROPPED_UNBOUND

    def _render_surface(self, surface: Surface) -> None:
        if self._size[1] <= 0:
            return
        y = surface.height - self._size[1]
        sub = surface.subsurface(y, 0, self._size[0], self._size[1])
        self._child._render_surface(sub)

    def hide(self) -> None:
        """Close the sheet."""
        self.open = False

    def resize(self, size: tuple[int, int]) -> None:
        """Resize the sheet and its child to the given terminal size."""
        self._size = (size[0], min(self._target_height, size[1] // 2))
        self._child.resize(self._size)
