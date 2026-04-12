# -*- coding: utf-8 -*-
"""
Module: pigit/termui/components_overlay.py
Description: Popup (layout/control), bordered HelpPanel, and Alert overlay parts.
Author: Zev
Date: 2026-04-01
"""

from __future__ import annotations

import logging
from typing import Any, Callable, ClassVar, Optional

from pigit.termui.bindings import resolve_key_handlers_merged
from pigit.termui.components import Component, _looks_like_overlay_host
from pigit.termui import keys
from pigit.termui.overlay_kinds import OverlayDispatchResult, OverlayKind
from pigit.termui.text import sanitize_for_display

_LOG = logging.getLogger(__name__)

HelpEntry = tuple[str, str]

# Box-drawing (UTF-8).
_BOX_H = "\u2500"
_BOX_V = "\u2502"
_BOX_TL = "\u250c"
_BOX_TR = "\u2510"
_BOX_BL = "\u2514"
_BOX_BR = "\u2518"


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

    def resize(self, size: tuple[int, int]) -> None:
        tw, th = int(size[0]), int(size[1])
        inner_w = (
            self._inner_w_cfg if self._inner_w_cfg is not None else max(24, tw // 2)
        )
        inner_h = (
            self._inner_h_cfg if self._inner_h_cfg is not None else max(8, th // 2)
        )
        inner_w = max(16, min(inner_w, tw - 4))
        inner_h = max(5, min(inner_h, th - 4))
        self._outer_w = inner_w + 2
        inner_rows = inner_h
        self._scroll_h = max(1, inner_rows - 1)
        self._inner_w = inner_w
        self.outer_row_count = inner_rows + 2
        self.fresh()

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

    def _render(self, size: Optional[tuple[int, int]] = None) -> None:
        if self._renderer is None:
            return
        inner = self._inner_w
        ow = self._outer_w
        title = " Help   esc close "
        title_vis = title[:inner].ljust(inner)
        frame: list[str] = []
        frame.append(_BOX_TL + _BOX_H * (ow - 2) + _BOX_TR)
        frame.append(_BOX_V + title_vis + _BOX_V)
        chunk = self._lines[self._offset : self._offset + self._scroll_h]
        padded = list(chunk)
        while len(padded) < self._scroll_h:
            padded.append("")
        for row in padded:
            inner_line = row[:inner].ljust(inner)
            frame.append(_BOX_V + inner_line + _BOX_V)
        frame.append(_BOX_BL + _BOX_H * (ow - 2) + _BOX_BR)
        self._renderer.draw_panel(frame, self.x, self.y, self._size)


class Popup(Component):
    """
    Modal shell around one inner :class:`~pigit.termui.components.Component`.

    Pass ``session_owner`` to resolve the :class:`~pigit.termui.overlay_host.OverlayHostMixin`
    root the same way as :class:`AlertDialog` (``session_owner`` may be the host itself or an
    ancestor walk via :meth:`~pigit.termui.components.Component.nearest_overlay_host`).
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
        if host.overlay_kind == OverlayKind.POPUP and host._active_popup is not None:
            if host._active_popup is not self:
                return
            host.end_popup_session()
            self.hide()
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
        self._child._size = (ow, row + oh - 1)

    def fresh(self) -> None:
        pass

    def _on_exit_key(self) -> None:
        if self._session_owner is not None:
            self._sync_popup_exit_with_host()
        else:
            raise NotImplementedError(
                "Subclass Popup without session_owner must override _on_exit_key."
            )

    def _render(self, size: Optional[tuple[int, int]] = None) -> None:
        self._sync_renderer_from_session_owner()
        if not self.open or self._renderer is None:
            return
        self._child._renderer = self._renderer
        self._child._render()


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
        self._frame_lines: list[str] = []
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
        self._rebuild_frame()

    def reset_state(self) -> None:
        self.open = False

    def resize(self, size: tuple[int, int]) -> None:
        self._term_cols = int(size[0])
        self._term_lines = int(size[1])
        self._rebuild_frame()
        super().resize(size)

    def _rebuild_frame(self) -> None:
        inner_w = (
            self._inner_w_cfg
            if self._inner_w_cfg is not None
            else max(20, self._term_cols // 2)
        )
        inner_w = max(16, min(inner_w, self._term_cols - 4))
        self._inner_w = inner_w
        self._frame_lines = self._build_bordered_frame()
        self._outer_w = inner_w + 2
        self.outer_row_count = len(self._frame_lines)

    def fresh(self) -> None:
        pass

    def _confirm(self) -> None:
        self._shell._finish_alert(True)

    def _render(self, size: Optional[tuple[int, int]] = None) -> None:
        if not self.open or self._renderer is None:
            return
        if not self._frame_lines:
            self._rebuild_frame()
        self._renderer.draw_panel(self._frame_lines, self.x, self.y, self._size)

    def _build_bordered_frame(self) -> list[str]:
        inner = self._inner_w
        ow = inner + 2
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
        frame: list[str] = []
        frame.append(_BOX_TL + _BOX_H * (ow - 2) + _BOX_TR)
        title_vis = " Alert "[:inner].ljust(inner)
        frame.append(_BOX_V + title_vis + _BOX_V)
        for line in wrapped:
            frame.append(_BOX_V + line[:inner].ljust(inner) + _BOX_V)
        frame.append(_BOX_V + " " * inner + _BOX_V)
        for fl in footer_lines:
            frame.append(_BOX_V + fl[:inner].ljust(inner) + _BOX_V)
        frame.append(_BOX_BL + _BOX_H * (ow - 2) + _BOX_BR)
        return frame


class AlertDialog(Popup):
    """
    Confirmation UI as a :class:`Popup` shell around :class:`AlertDialogBody`.

    Call :meth:`alert` from application code with a message and ``on_result`` callback.
    Opening uses :meth:`~pigit.termui.components_overlay.Popup.show` and host
    :meth:`~pigit.termui.overlay_host.OverlayHostMixin.begin_popup_session`; closing uses
    :meth:`~pigit.termui.overlay_host.OverlayHostMixin.end_popup_session` and
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
        if host is None or host.overlay_kind != OverlayKind.NONE:
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
