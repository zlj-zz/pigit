"""
Module: pigit/termui/root.py
Description: Internal framework root that wraps body + LayerStack.
Author: Zev
Date: 2026-08-20
"""

from __future__ import annotations

import time
from dataclasses import replace
from typing import TYPE_CHECKING, Any, Literal
from collections.abc import Callable

from .component import Component, resolve_focus_leaf
from ._layer import LayerKind, LayerStack
from .mouse import MouseEvent
from .event_bus import EventBus
from .types import OverlayDispatchResult
from ._runtime_context import FocusManager
from .overlay import get_badge_signal
from .widgets.sheet import DEFAULT_MAX_FRACTION

if TYPE_CHECKING:
    from ._runtime_context import ComponentRegistry
    from .surface import Surface
    from .widgets import Sheet


class ComponentRoot(Component):
    """
    Internal framework root: wraps the user body component and manages overlays.

    Single keyboard entry for ``AppEventLoop``: overlay, then root-level
    bindings / ``handle_key``, then the focus leaf. Not exported in the
    public termui API.
    """

    def __init__(
        self,
        body: Component,
        registry: ComponentRegistry | None = None,
        event_bus: EventBus | None = None,
        *,
        key_handlers: dict[str, Callable[..., Any]] | None = None,
        handle_key: Callable[[str], bool] | None = None,
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
        # Rows reserved below bottom-anchored toasts (app chrome like footer).
        self.toast_bottom_pad = 0
        self._event_bus = event_bus
        self._app_on_event: Callable | None = None
        self._event_loop: Any | None = None
        self._root_handle_key = handle_key
        self._dispatch_depth = 0
        if key_handlers:
            self._key_handlers.update(key_handlers)

    def mount(self) -> None:
        """Activate the root and propagate mount to the body component tree."""
        super().mount()
        self._body.mount()
        # Reset stale badge from previous sessions.
        sig = get_badge_signal()
        if sig.value is not None:
            sig.set(None)

    def destroy(self) -> None:
        """Destroy children. Runtime context is reset by the caller."""
        self._body.destroy()
        super().destroy()

    @property
    def body(self) -> Component:
        """The root's single child component (the application body)."""
        return self._body

    @property
    def event_bus(self) -> EventBus | None:
        """The framework event bus used for cross-panel subscriptions."""
        return self._event_bus

    def __del__(self) -> None:
        """Best-effort cleanup: nothing to do; bus is owned by Application."""
        pass

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

    def is_presentation_stolen(self) -> bool:
        """True while an open MODAL or SHEET owns keyboard chrome (not TOAST)."""
        return self._top_open_overlay() is not None

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

    def paint(self, surface: Surface) -> None:
        self._expire_toasts()
        self._expire_badge()
        self._body.paint(surface)
        self._layer_stack.render(surface)

    def _top_open_overlay(self) -> Component | None:
        for kind in (LayerKind.MODAL, LayerKind.SHEET):
            top = self._layer_stack.top(kind)
            if top is not None and getattr(top, "open", False):
                return top
        return None

    def _sync_focus_if_overlay_changed(self, overlay_was_open: bool) -> None:
        """Re-resolve focus when a root handler opened or closed an overlay."""
        if overlay_was_open != self.has_overlay_open():
            self._focus_manager.sync_focus_to_overlay_or_leaf()

    def _handle_event(self, key: str) -> bool:
        """Dispatch overlay, then the focus leaf, then root/app bindings.

        The focused component tree runs before app-global bindings so that a
        modal inline input (``capture_key``) and the focus leaf's own bindings
        win over universal shortcuts. Root bindings are the fallback for keys
        the tree declined; re-entry from a leaf bubble returns False so those
        fallbacks run exactly once.
        """
        if self._dispatch_depth:
            return False
        self._dispatch_depth += 1
        try:
            overlay_was_open = self.has_overlay_open()
            result = self.try_dispatch_overlay(key)
            if result != OverlayDispatchResult.DROPPED_UNBOUND:
                self._focus_manager.sync_focus_to_overlay_or_leaf()
                return True

            leaf = self._focus_manager.get_focus_leaf() or resolve_focus_leaf(
                self._body
            )
            if leaf is not None:
                consumed = leaf._handle_event(key)
                self._focus_manager.sync_focus_to_overlay()
                if consumed:
                    return True
            else:
                self._focus_manager.sync_focus_to_overlay()
                return False

            # App-global shortcuts: the tree declined, so give them a turn.
            handler = self._key_handlers.get(key)
            if handler is not None:
                handler()
                self._sync_focus_if_overlay_changed(overlay_was_open)
                return True

            if self._root_handle_key is not None and self._root_handle_key(key):
                self._sync_focus_if_overlay_changed(overlay_was_open)
                return True
            return False
        finally:
            self._dispatch_depth -= 1

    def _handle_mouse(self, event: MouseEvent) -> bool:
        """Route a mouse event: overlays first, then body with click-to-focus.

        MODAL swallows clicks that miss it (it is a centered dialog). A SHEET
        is an edge overlay, so a click outside it falls through to the body —
        the rest of the app stays clickable while the sheet is open.
        """
        modal = self._layer_stack.top(LayerKind.MODAL)
        if modal is not None and getattr(modal, "open", False):
            hit = modal._hit_test(event.col, event.row)
            if hit is None:
                return True
            target, lcol, lrow = hit
            target.handle_mouse(replace(event, col=lcol, row=lrow))
            self._focus_manager.sync_focus_to_overlay_or_leaf()
            return True

        sheet = self._layer_stack.top(LayerKind.SHEET)
        if sheet is not None and getattr(sheet, "open", False):
            hit = sheet._hit_test(event.col, event.row)
            if hit is not None:
                target, lcol, lrow = hit
                target.handle_mouse(replace(event, col=lcol, row=lrow))
                return True

        hit = self._body._hit_test(event.col, event.row)
        if hit is None:
            return False
        target, lcol, lrow = hit
        self.focus_component(target)
        target.handle_mouse(replace(event, col=lcol, row=lrow))
        return True

    def focus_component(self, leaf: Component) -> None:
        """Move focus to ``leaf`` through its focus-managed ancestor containers.

        Only a focus-managed ``Column`` routes focus: clicking one of its
        children switches ``_focus_index``. ``TabView`` never needs this — its
        ``_hit_test`` only returns the active child, so a click cannot land on
        a non-active tab. When no focus-managed ancestor is on the path
        (e.g. clicking the header or footer), focus is left unchanged so
        keyboard focus is not stolen by a non-focusable click.
        """
        from .containers import Column

        path: list[Component] = []
        node: Component | None = leaf
        while node is not None and node is not self._body:
            path.append(node)
            node = node.parent
        path.append(self._body)

        changed = False
        for i in range(len(path) - 1, 0, -1):
            parent, child = path[i], path[i - 1]
            if isinstance(parent, Column) and parent._focus_index is not None:
                idx = parent.children.index(child)
                if parent._focus_index != idx:
                    parent.set_focus_index(idx)
                    changed = True

        if changed:
            self._focus_manager.set_focus_chain(resolve_focus_leaf(self._body))

    def _expire_badge(self) -> None:
        if getattr(self, "_badge_until", 0) and time.monotonic() > self._badge_until:
            self.hide_badge()

    def _expire_toasts(self) -> None:
        top = self._layer_stack.top(LayerKind.TOAST)
        if top is not None and top.is_expired():
            self._pop_layer(LayerKind.TOAST)

    def show_sheet(
        self,
        child: Component,
        height: int | None = None,
        *,
        max_fraction: float = DEFAULT_MAX_FRACTION,
        show_edge_rule: bool = True,
        title: str | None = None,
        title_align: Literal["left", "center", "right"] = "right",
        edge: Literal["top", "bottom"] = "bottom",
        bg: tuple[int, int, int] | None = None,
    ) -> Sheet:
        """Display a sheet on the SHEET layer and move focus to its leaf.

        Height resolution matches :func:`~pigit.termui.overlay.show_sheet`:
        omitted ``height`` uses the child's preferred height and
        ``max_fraction``; an explicit ``height`` only gets the half-terminal
        safety clamp. Optional ``title`` embeds in the facing-edge rule.
        """
        from .widgets import Sheet

        term_h = self._size[1] if self._size[1] > 0 else 24
        resolved = Sheet.resolve_height(
            child,
            term_h,
            height=height,
            max_fraction=max_fraction,
        )
        sheet = Sheet(
            child,
            resolved,
            show_edge_rule=show_edge_rule,
            title=title,
            title_align=title_align,
            edge=edge,
            bg=bg,
        )
        sheet.resize(self._size)
        self._layer_stack.push(LayerKind.SHEET, sheet)
        # Focus must track the stack here so body panels dim on the first frame
        # (is_focus_leaf), including AsyncTask / non-key open paths.
        self._focus_manager.sync_focus_to_overlay_or_leaf()
        return sheet

    def dismiss_sheet(self) -> None:
        """Dismiss the current sheet, if any, and restore body focus."""
        self._pop_layer(LayerKind.SHEET)
        self._focus_manager.sync_focus_to_overlay_or_leaf()

    def _pop_layer(self, kind: LayerKind) -> None:
        overlay = self._layer_stack.pop(kind)
        if overlay is not None:
            overlay.hide()
