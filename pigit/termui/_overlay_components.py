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
from typing import Any, Callable, ClassVar, Optional, TYPE_CHECKING

from pigit.termui._bindings import resolve_key_handlers_merged

from ._component_base import Component, _looks_like_overlay_host
from .types import ToastPosition, OverlayDispatchResult, LayerKind
from ._frame import BoxFrame
from ._text import sanitize_for_display
from ._layout import Padding
from ._geometry import TerminalSize
from ._surface import Surface
from pigit.termui import keys
from pigit.termui.wcwidth_table import truncate_by_width

_LOG = logging.getLogger(__name__)

# Maximum number of lines to display in a Toast (safety limit)
MAX_TOAST_LINES = 100

HelpEntry = tuple[str, str]


class HelpPanel(Component):
    """
    Plain help content (bordered, scrollable key list). Not modal until wrapped.

    Use :class:`Popup` with ``session_owner`` set to a :class:`~pigit.termui.components.Component`
    that can reach the modal host (typically the loop root or a panel under it); the shell
    resolves the host via :meth:`~pigit.termui.components.Component.nearest_overlay_host` or
    treats ``session_owner`` as the host when it owns overlay state. Bind ``?`` to a handler that
    refreshes rows (e.g. :meth:`merge_help_entries_from_host_children`) when opening help,
    then calls ``popup.toggle()``.

    :data:`TOGGLE_HELP_SEMANTIC_KEYS` lists keys that toggle help while this panel's
    wrapping :class:`Popup` is active; overlay routing calls
    :meth:`Popup.dispatch_overlay_key`, which runs :meth:`Popup.toggle` for those keys
    when shell and child bindings do not handle them.
    """

    NAME = "help"

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
        renderer: Any = None,
    ) -> None:
        super().__init__(x=x, y=y, size=size, renderer=renderer)
        self._inner_w_cfg = inner_width
        self._inner_h_cfg = inner_height
        self._lines: list[str] = []
        self._offset = 0
        self._inner_w = 40
        self._scroll_h = 6
        self._outer_w = 42
        self.outer_row_count = 10
        self._frame = BoxFrame(0, 0, title="Help   esc close")
        self._padding = Padding(top=2, right=4, bottom=2, left=4)

    def resize(self, size: tuple[int, int]) -> None:
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
        lines: list[str] = []
        for key_disp, desc in entries:
            lines.append(f"{key_disp}  {desc}")
        self._lines = lines
        self._offset = 0

    def merge_help_entries_from_host_children(
        self, host: Any, *, max_rows: int = 256
    ) -> None:
        """
        Build help rows from ``host.children``: collect
        :meth:`~pigit.termui.components.Component.get_help_entries` from each mapped child,
        then :meth:`set_entries` (truncated to ``max_rows``).

        This is independent of how or when the panel is shown; call it from app code when
        you want the list to reflect the current tree (e.g. before opening help).
        """

        children = getattr(host, "children", None)
        if children is None:
            raise TypeError(
                "Host must expose a non-optional `children` mapping (e.g. Container root)."
            )
        rows: list[HelpEntry] = []
        for panel in children.values():
            rows.extend(panel.get_help_entries())
        self.set_entries(rows[:max_rows])

    def scroll_down(self) -> None:
        max_off = max(0, len(self._lines) - self._scroll_h)
        self._offset = min(self._offset + 1, max_off)

    def scroll_up(self) -> None:
        self._offset = max(0, self._offset - 1)

    def fresh(self) -> None:
        pass

    def _render_surface(self, surface: Surface) -> None:
        self._frame.draw_onto(surface, self.x, self.y)

        chunk = self._lines[self._offset : self._offset + self._scroll_h]
        self._frame.draw_content(surface, self.x, self.y, chunk)


class Popup(Component):
    """
    Modal shell around one inner :class:`~pigit.termui.components.Component`.

    Pass ``session_owner`` to resolve the overlay host (usually
    :class:`~pigit.termui.root.ComponentRoot`) the same way as :class:`AlertDialog`
    (``session_owner`` may be the host itself or an ancestor walk via
    :meth:`~pigit.termui.components.Component.nearest_overlay_host`).
    :meth:`toggle` and ``exit_key`` then coordinate ``begin_popup_session`` /
    ``end_popup_session`` when ``session_owner`` is set.

    When ``session_owner`` is set, :meth:`_render` pulls the shared :class:`~pigit.termui.render.Renderer`
    from ``session_owner`` (or its ``parent`` chain) so side-attached shells need no
    ``AppEventLoop``-specific attribute names.

    Subclasses that omit ``session_owner`` must override :meth:`_on_exit_key`. Wrapped
    content may declare :data:`TOGGLE_HELP_SEMANTIC_KEYS` so :meth:`_fallback_overlay_key`
    calls :meth:`toggle` for those keys when ``session_owner`` is set.
    """

    NAME = "popup"

    def __init__(
        self,
        child: Component,
        *,
        session_owner: Optional[Component] = None,
        offset: Optional[tuple[int, int]] = None,
        exit_key: str = keys.KEY_ESC,
        x: int = 1,
        y: int = 1,
        size: Optional[tuple[int, int]] = None,
        renderer: Any = None,
    ) -> None:
        self._child = child
        self._offset = offset
        self.exit_key = exit_key
        self._session_owner = session_owner
        self.open = False
        self._term_size: tuple[int, int] = (80, 24)

        self.BINDINGS = [(exit_key, "_on_exit_key")]
        super().__init__(x=x, y=y, size=size, renderer=renderer)

    def _resolved_overlay_host(self) -> Optional[Component]:
        """
        Return the overlay host for this shell, without requiring ``self`` to be parent-linked.

        If ``session_owner`` is the host (e.g. loop root), use it; else walk from
        ``session_owner`` via :meth:`~pigit.termui.components.Component.nearest_overlay_host`.
        """

        owner = self._session_owner
        if owner is None:
            return None
        if _looks_like_overlay_host(owner):
            return owner
        return owner.nearest_overlay_host()

    def _sync_renderer_from_session_owner(self) -> None:
        """
        If this shell has no ``_renderer`` yet, copy from ``session_owner`` or an ancestor
        that already received the loop's renderer (side-attached popups are not in ``children``).
        """

        if self._renderer is not None:
            return
        owner = self._session_owner
        if owner is None:
            return
        cur: Optional[Component] = owner
        while cur is not None:
            r = getattr(cur, "_renderer", None)
            if r is not None:
                self._renderer = r
                inner = self._child
                if inner is not None and getattr(inner, "_renderer", None) is None:
                    inner._renderer = r
                return
            cur = cur.parent

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

    @staticmethod
    def _invoke_binding_target(target: Component, key: str) -> bool:
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
        if self._session_owner is not None and key in toggle_keys:
            if self._resolved_overlay_host() is None:
                return OverlayDispatchResult.DROPPED_UNBOUND
            self.toggle()
            return OverlayDispatchResult.HANDLED_IMPLICIT
        return OverlayDispatchResult.DROPPED_UNBOUND

    def toggle(self) -> None:
        if self._session_owner is None:
            return
        host = self._resolved_overlay_host()
        if host is None:
            return
        layer_stack = getattr(host, '_layer_stack', None)
        if layer_stack is None:
            return
        top = layer_stack.top(LayerKind.MODAL)
        if top is self:
            host.end_popup_session()
            self.hide()
            return
        if top is not None:
            # Another modal is active; do not steal focus.
            return
        self.show()
        host.begin_popup_session(self)

    def _sync_popup_exit_with_host(self) -> None:
        host = self._resolved_overlay_host()
        if host is None:
            self.hide()
            return
        host.end_popup_session()
        self.hide()

    def show(self) -> None:
        self.open = True

    def hide(self) -> None:
        self.open = False

    def resize(self, size: tuple[int, int]) -> None:
        self._term_size = (int(size[0]), int(size[1]))
        self._child.resize(size)
        self._layout_content()
        self.fresh()

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
            row = 1 + max(0, (th - oh) // 2)
            col = 1 + max(0, (tw - ow) // 2)
        else:
            row, col = int(self._offset[0]), int(self._offset[1])
        self._child.x = row
        self._child.y = col
        self._child._size = (ow, oh)

    def fresh(self) -> None:
        pass

    def _on_exit_key(self) -> None:
        if self._session_owner is not None:
            self._sync_popup_exit_with_host()
        else:
            raise NotImplementedError(
                "Subclass Popup without session_owner must override _on_exit_key."
            )

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

    NAME = "alert_dialog_body"

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
        renderer: Any = None,
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
        self._frame = BoxFrame(0, 0, title="Alert")
        self.BINDINGS = [(self._confirm_key, "_confirm")]
        super().__init__(x=x, y=y, size=size, renderer=renderer)

    def open_alert(self) -> None:
        if self.open:
            return
        self.open = True

    def prepare(self, message: str, on_result: Callable[[bool], None]) -> None:
        self._message = sanitize_for_display(message)
        self._on_result = on_result
        self.open_alert()
        self._needs_rebuild = True

    def reset_state(self) -> None:
        self.open = False

    def resize(self, size: tuple[int, int]) -> None:
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

    def fresh(self) -> None:
        pass

    def _confirm(self) -> None:
        self._shell._finish_alert(True)

    def _render_surface(self, surface: Surface) -> None:
        if not self.open:
            return
        if self._needs_rebuild:
            self._rebuild_frame()
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
    Opening uses :meth:`~pigit.termui.components_overlay.Popup.show` and host
    ``begin_popup_session``; closing uses ``end_popup_session`` and
    :meth:`~pigit.termui.components_overlay.Popup.hide`.

    Panels typically set ``_alert_dialog`` and ``_alert_popup`` to this same instance.
    """

    NAME = "alert_dialog"

    def __init__(
        self,
        session_owner: Component,
        x: int = 1,
        y: int = 1,
        size: Optional[tuple[int, int]] = None,
        inner_width: Optional[int] = None,
        on_result: Optional[Callable[[bool], None]] = None,
        confirm_key: str = keys.KEY_ENTER,
        cancel_key: str = keys.KEY_ESC,
        renderer: Any = None,
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
            renderer=renderer,
        )
        super().__init__(
            self._pane,
            session_owner=session_owner,
            offset=None,
            exit_key=keys.KEY_ESC,
            x=x,
            y=y,
            size=size,
            renderer=renderer,
        )

    def _on_exit_key(self) -> None:
        self._finish_alert(False)

    def alert(self, message: str, on_result: Callable[[bool], None]) -> bool:
        """
        Prepare content, show this popup, and register the overlay host alert session.

        Returns:
            True if the dialog was shown; False if no host or another overlay is active.
        """

        host = self._resolved_overlay_host()
        if host is None:
            return False
        # Only block if another MODAL is already open (TOAST/SHEET are non-blocking).
        layer_stack = getattr(host, '_layer_stack', None)
        if layer_stack is not None:
            if layer_stack.top(LayerKind.MODAL) is not None:
                return False
        elif host.has_overlay_open():
            return False
        self._pane.prepare(message, on_result)
        self.relayout_content()
        self.show()
        host.begin_popup_session(self)
        return True

    def _finish_alert(self, value: bool) -> None:
        fn = self._pane._on_result
        host = self._resolved_overlay_host()
        if host is not None:
            host.end_popup_session()
        else:
            _LOG.warning(
                "AlertDialog finished without an overlay host in the parent chain; "
                "if begin_popup_session ran, root overlay_kind may stay stale."
            )
        self.hide()
        self._pane.reset_state()
        if fn is None:
            return
        try:
            fn(value)
        except Exception:
            _LOG.exception("AlertDialog on_result failed")

    def reset_state(self) -> None:
        """Clear body state and hide the shell (e.g. after host error recovery)."""

        self.hide()
        self._pane.reset_state()

    def resize(self, size: tuple[int, int]) -> None:
        super().resize(size)


class Toast(Component):
    """自动消失的通知消息（TOAST 层），支持边框、动画和可配置位置。"""

    NAME = "toast"

    def __init__(
        self,
        message: str,
        duration: float = 2.0,
        size: Optional[tuple[int, int]] = None,
        clock: Callable[[], float] = time.monotonic,
        position: ToastPosition = ToastPosition.TOP_RIGHT,
        enter_duration: float = 0.5,
        exit_duration: float = 0.5,
    ) -> None:
        super().__init__(size=size)
        self._message = message
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
        return self._clock() - self._created_at > self.duration + self._exit_duration

    def resize(self, size: tuple[int, int]) -> None:
        new_size = (int(size[0]), int(size[1]))
        if self._term_size != new_size:
            self._term_size = new_size
            self._needs_rebuild = True
        super().resize(size)

    def _rebuild_frame(self) -> None:
        """根据当前终端尺寸重建 BoxFrame 和内容行。"""
        max_inner_w = max(0, self._term_size[0] - 4)
        lines = [
            truncate_by_width(line, max_inner_w)
            for line in self._message.split("\n")
        ]
        # Safety limit to prevent memory issues with malicious input
        self._lines = lines[:MAX_TOAST_LINES]
        inner_h = len(self._lines)
        inner_w = max(len(line) for line in self._lines) if self._lines else 0

        if self._frame is None:
            self._frame = BoxFrame(inner_w, inner_h)
        else:
            self._frame.set_inner_size(inner_w, inner_h)
        self._outer_w = self._frame.outer_width
        self.outer_row_count = self._frame.outer_height
        self._needs_rebuild = False

    def _compute_slide_offset(self, elapsed: float) -> int:
        """计算水平方向动画偏移量。

        Args:
            elapsed: 从创建到现在经过的秒数。

        Returns:
            相对于目标位置的列偏移（目标位置为0）。
            LEFT_*: 负值表示在目标左侧（屏幕外）
            RIGHT_*: 正值表示在目标右侧（屏幕外）
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
        """计算目标位置的 (row, col)，不含动画偏移。"""
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

        self._frame.draw_onto(surface, base_row, render_col)
        self._frame.draw_content(surface, base_row, render_col, self._lines)

    @property
    def message(self) -> str:
        """Toast message content (backward compatibility)."""
        return self._message

    def hide(self) -> None:
        self.open = False

    def fresh(self) -> None:
        pass


class Sheet(Component):
    """底部滑出面板，类似移动端的 bottom sheet（SHEET 层）。"""

    NAME = "sheet"

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
        if self._child_dispatch is not None:
            return self._child_dispatch(key)
        return OverlayDispatchResult.DROPPED_UNBOUND

    def _render_surface(self, surface: Surface) -> None:
        if self._size[1] <= 0:
            return
        y = surface.height - self._size[1]
        sub = surface.subsurface(0, y, self._size[0], self._size[1])
        self._child._render_surface(sub)

    def hide(self) -> None:
        self.open = False

    def resize(self, size: tuple[int, int]) -> None:
        self._size = (size[0], min(self._target_height, size[1] // 2))
        self._child.resize(self._size)
