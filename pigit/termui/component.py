"""
Module: pigit/termui/component.py
Description: Base Component class and related utilities for the TUI framework.
Author: Zev
Date: 2026-08-20
"""

from __future__ import annotations

import logging
from abc import ABC
from dataclasses import dataclass
from typing import Any, Literal, TYPE_CHECKING
from collections.abc import Callable, Sequence

from .bindings import (
    BindingsList,
    derive_executable_bindings,
    derive_help_entries,
    join_footer_display_pairs,
    merge_footer_pairs,
    resolve_action_keys,
    resolve_instance_bindings,
)
from .mouse import MouseEvent
from ._runtime_context import (
    get_focus_manager,
    get_overlay_host,
    get_renderer,
    get_renderer_strict,
)
from .reactive import Computed, Signal
from .theme import get_theme
from .types import EventType, OverlayDispatchResult

if TYPE_CHECKING:
    from .renderer import Renderer
    from .surface import Surface

_logger = logging.getLogger(__name__)

NONE_SIZE = (0, 0)


@dataclass(eq=False)
class _Subscription:
    """Internal record tracking a framework-level event subscription."""

    action: EventType
    handler: Callable[..., bool | None]
    pending: bool = True
    unsub: Callable[[], None] | None = None

    def cancel(self) -> None:
        if self.unsub is not None:
            self.unsub()


class ComponentError(Exception):
    """Error class of ~Component."""


def render_child(component: Component, surface: Surface, log_prefix: str = "") -> None:
    """Blit ``component`` into ``surface`` using the child's x/y/_size (1-based).

    Args:
        component: Child component to render into ``surface``.
        surface: Target draw surface (1-based child coords are converted internally).
        log_prefix: Prefix for invalid-coordinate warning logs.
    """
    w, h = component._size
    if w <= 0 or h <= 0:
        return
    if component.x < 1 or component.y < 1:
        _logger.warning(
            "%s %s with invalid 1-based coords (%s, %s)",
            log_prefix,
            type(component).__name__,
            component.x,
            component.y,
        )
    sub = surface.subsurface(max(0, component.x - 1), max(0, component.y - 1), w, h)
    component.paint(sub)


class Component(ABC):
    """Base class for all TUI components.

    Skeleton class containing tree structure, geometry, rendering,
    key handling, event bubbling, and lifecycle hooks.
    Subclasses must implement :meth:`paint`.
    """

    BINDINGS: BindingsList | None = None
    TAB_NAME: str = ""
    tab_key: str = ""

    @property
    def tab_name(self) -> str:
        """Header tab label for this component."""
        return self.TAB_NAME

    def __init__(
        self,
        x: int = 1,
        y: int = 1,
        size: tuple[int, int] | None = None,
        children: Sequence[Component] | None = None,
        parent: Component | None = None,
        id: str | None = None,
    ) -> None:
        self._mounted = False
        self._focus_level: int = -1

        self.x, self.y = x, y
        self._size = size or NONE_SIZE

        self.parent = parent
        self.children = list(children) if children else []

        self.id = id
        self._bind_signal_handlers: list[object] = []
        self._try_register_id()

        self._action_bindings, self._key_handlers = resolve_instance_bindings(self)
        self._subscriptions: list[_Subscription] = []

    def mount(self):
        """Enter the live component tree (subscriptions / async gate).

        Not the same as becoming visible or focused — exclusive hosts may keep
        mounted children hidden.
        """
        self._unsubscribe_all()
        self._replay_pending_subscriptions()
        self._mounted = True

    def unmount(self):
        """Leave the live component tree; drop framework subscriptions."""
        self._unsubscribe_all()
        self._mounted = False

    def is_mounted(self):
        """True while this component is on the live session tree."""
        return self._mounted

    def on_focus(self) -> None:
        """Called when this component becomes the focused child of a focus host.

        Warm-focus containers (e.g. Column) invoke this on focus changes without
        unmounting siblings. Override to refresh data that must be current when
        the user looks at this panel.
        """

    def on_hide(self) -> None:
        """Called when an exclusive parent stops painting this child.

        The child remains mounted. Override to pause background work that should
        not run while covered (e.g. DiffViewer patch/tokenize).
        """

    def exclusive_visible_child(self) -> Component | None:
        """If this node paints exactly one child, return it; else ``None``.

        Exclusive-visible containers override this so
        :func:`is_on_visible_paint_path` does not need a closed set of
        ``isinstance`` checks.
        """
        return None

    def subscribe(
        self,
        action: EventType,
        handler: Callable[..., bool | None],
    ) -> Callable[[], None]:
        """Subscribe to a framework-level event.

        If the component is not yet mounted under a root with an event bus,
        the subscription is queued and replayed on :meth:`mount`. The returned
        callback unsubscribes the handler.
        """
        from .root import ComponentRoot

        root = self._root_component()
        bus = root.event_bus if isinstance(root, ComponentRoot) else None
        sub = _Subscription(action=action, handler=handler)
        self._subscriptions.append(sub)

        if bus is not None:
            sub.pending = False
            sub.unsub = bus.subscribe(action, handler)
        else:
            sub.pending = True

        def delayed_unsub() -> None:
            if sub.pending:
                try:
                    self._subscriptions.remove(sub)
                except ValueError:
                    pass
                return
            sub.cancel()
            try:
                self._subscriptions.remove(sub)
            except ValueError:
                pass

        return delayed_unsub

    def _replay_pending_subscriptions(self) -> None:
        from .root import ComponentRoot

        root = self._root_component()
        bus = root.event_bus if isinstance(root, ComponentRoot) else None
        if bus is None:
            return
        for sub in self._subscriptions:
            if sub.pending:
                sub.pending = False
                sub.unsub = bus.subscribe(sub.action, sub.handler)

    def _unsubscribe_all(self) -> None:
        """Cancel active subscriptions and remove them from the list."""
        for sub in list(self._subscriptions):
            if not sub.pending:
                sub.cancel()
                self._subscriptions.remove(sub)

    def _root_component(self) -> Any:
        """Walk parent chain to find the ComponentRoot, if mounted."""
        from .root import ComponentRoot

        node = self.parent
        while node is not None:
            if isinstance(node, ComponentRoot):
                return node
            node = node.parent
        return None

    def _try_register_id(self) -> None:
        """Register with the global component registry if an id is set."""
        if not self.id:
            return
        from ._runtime_context import get_registry

        reg = get_registry()
        if reg is not None:
            reg.register(self)

    def _try_unregister_id(self) -> None:
        """Unregister from the global component registry if an id is set."""
        if not self.id:
            return
        from ._runtime_context import get_registry

        reg = get_registry()
        if reg is not None:
            reg.unregister(self)

    def destroy(self) -> None:
        """Destroy children and unregister from component registry."""
        self.unmount()
        for child in self.children:
            child.destroy()
        self._try_unregister_id()

    def hide(self) -> None:
        """Close or hide this component. No-op by default; overlays override."""

    @property
    def size(self) -> tuple[int, int]:
        """Current (width, height) assigned by the last resize()."""
        return self._size

    def global_origin(self) -> tuple[int, int]:
        """0-based (row, col) of this component's top-left on the terminal.

        Each ancestor stores a parent-relative 1-based ``x`` (row) / ``y``
        (col); summing ``coord - 1`` along the parent chain yields the screen
        position.
        """
        row = 0
        col = 0
        node: Component | None = self
        while node is not None:
            row += max(0, int(getattr(node, "x", 1)) - 1)
            col += max(0, int(getattr(node, "y", 1)) - 1)
            node = getattr(node, "parent", None)
        return row, col

    def refresh(self):
        """Fresh content data.

        Default is no-op; override if the component needs to rebuild internal
        state when resized or notified.
        """

    def resize(self, size: tuple[int, int]) -> None:
        """Response to the resize event.

        Subclasses that manage child geometry (e.g. Column, Row, TabView)
        must override this method to propagate the correct size to each child.

        An unchanged size skips ``refresh`` so per-frame relayouts (e.g. a
        header laying out its slot children on every paint) do not re-request
        a render and spin the event loop.
        """
        if self._size == size:
            return
        self._size = size
        self.refresh()

    def capture_key(self, key: str) -> bool:
        """Return True to consume the key before any binding.

        Override for modal input (e.g. an active text filter) that must
        intercept keys ahead of the component's key bindings.
        """
        return False

    def _handle_event(self, key: str) -> bool:
        """Process a key event. Delegates to the event dispatch algorithm."""
        from ._component_event import dispatch_key

        return dispatch_key(self, key)

    def handle_mouse(self, event: MouseEvent) -> bool:
        """Handle a mouse event at this component's local coordinates.

        Returns True when consumed. The default is False (not interactive);
        interactive components override this to map a click/wheel to an action.
        """
        return False

    def _handle_mouse(self, event: MouseEvent) -> bool:
        """Route a mouse event to this component (default: interpret directly).

        ``ComponentRoot`` overrides this to hit-test the tree and route to the
        component under the cursor; leaves interpret the event via
        :meth:`handle_mouse`.
        """
        return self.handle_mouse(event)

    def _hit_test(self, col: int, row: int) -> tuple[Component, int, int] | None:
        """Return the deepest component under 1-based ``(col, row)``.

        The result is ``(component, local_col, local_row)`` where the local
        coordinates are 1-based relative to the returned component. Mirrors
        rendering: children painted last are tested first, and a child's
        ``x``/``y`` (1-based, parent-relative) offset the recursion.
        """
        for child in reversed(self.children):
            w, h = child._size
            if w <= 0 or h <= 0:
                continue
            if not (child.y <= col < child.y + w and child.x <= row < child.x + h):
                continue
            hit = child._hit_test(col - (child.y - 1), row - (child.x - 1))
            if hit is not None:
                return hit
        return self, col, row

    def emit(self, action: EventType, **data) -> None:
        """Bubble action up through parent chain to Application.

        Stops at the first ancestor whose ``on_event`` returns True.
        If no handler consumes it, logs a warning.
        """
        from ._component_event import bubble_event

        bubble_event(self, action, **data)

    def notify(self, action: EventType, **data) -> None:
        """Notify all children by calling their ``update`` method."""
        from ._component_event import notify_children

        notify_children(self, action, **data)

    def paint(self, surface: Surface) -> None:
        """Draw this component into ``surface`` (override in subclasses)."""

    def has_overlay_open(self) -> bool:
        """Return True if an overlay is open. Base components never have overlays."""
        return False

    def try_dispatch_overlay(self, key: str) -> OverlayDispatchResult:
        """Dispatch a key to an overlay. Base components have no overlays."""
        return OverlayDispatchResult.DROPPED_UNBOUND

    def accept(self, action: EventType, **data) -> None:
        """Handle an action event broadcast from a parent container.

        Default is no-op; container components override this to route or
        broadcast to children.
        """

    def update(self, action: EventType, **data) -> None:
        """Receive an action update from a parent or sibling component.

        Default is no-op; interactive components override this to react to
        state changes (e.g. a panel refreshing when another panel changes).
        """

    @property
    def focus_child(self) -> Component | None:
        """Child that currently holds focus among this node's children.

        ``None`` means this node does not manage focus (not "I am the leaf").
        """
        return None

    @property
    def presentation_child(self) -> Component | None:
        """Chrome delegate. ``None`` means this node is the presentation unit."""
        return None

    @property
    def is_focus_leaf(self) -> bool:
        """Return True if this component is the resolved focus leaf."""
        return self._focus_level == 0

    def is_presentation_stolen(self) -> bool:
        """True while an open MODAL or SHEET owns keys (via overlay host)."""
        host = get_overlay_host()
        return host is not None and host.is_presentation_stolen()

    def is_presentation_active(self) -> bool:
        """True when structural colors use full primary/muted strength.

        False while a MODAL/SHEET steals keys, or while a focus manager has a
        leaf and this component is not that leaf. Headless (no focus manager
        / no leaf) stays active so unit tests keep role colors.
        """
        if self.is_presentation_stolen():
            return False
        fm = get_focus_manager()
        if (
            fm is not None
            and fm.get_focus_leaf() is not None
            and not self.is_focus_leaf
        ):
            return False
        return True

    def presentation_fg(
        self,
        role: Literal["primary", "muted"] = "primary",
    ) -> tuple[int, int, int]:
        """Return structural/metadata fg from presentation state.

        Resolution: steal → ``fg_inactive``; non-focus-leaf → primary→muted /
        muted→dim; else role color. Git semantic colors bypass this helper —
        pass ``THEME.fg_*`` / panel helpers directly.
        Cursor-axis contrast (non-cursor muted inside a list) stays in the caller.
        """
        theme = get_theme()
        if not self.is_presentation_active():
            if self.is_presentation_stolen():
                return theme.fg_inactive
            if role == "muted":
                return theme.fg_dim
            return theme.fg_muted
        if role == "muted":
            return theme.fg_muted
        return theme.fg_primary

    @property
    def renderer(self) -> Renderer | None:
        """Get the current renderer from context.

        Returns:
            The current Renderer instance, or None if not in event loop.
        """
        return get_renderer()

    @property
    def renderer_strict(self) -> Renderer:
        """Get renderer, raising if not available.

        Returns:
            The current Renderer instance.

        Raises:
            RendererNotBoundError: If not within AppEventLoop context.
        """
        return get_renderer_strict()

    def get_executable_bindings(self):
        """Derive executable help rows from ``@bind_action`` bindings."""
        return derive_executable_bindings(self._action_bindings, self)

    def get_help_entries(self) -> list[tuple[str, str]]:
        """Derive help entries from ``@bind_action`` bindings.

        Panels using ``@bind_action`` inherit this; panels may still override
        for fully custom help. Multi-key actions render their keys joined
        with ``/``.
        """
        return derive_help_entries(self._action_bindings, self)

    def get_footer_entries(self) -> list[tuple[str, str]]:
        """Derive the compact footer subset (bindings with a ``tip``).

        Bindings sharing the same ``tip`` are merged into one entry with their
        keys joined, saving horizontal space (e.g. ``j/k/down/up Navigate``).
        ``tip_when`` may hide a tip for the current state; help (``desc``) is
        unaffected. State-dependent actions handled by ``capture_key``/
        ``handle_key`` (not ``@bind_action``) are intentionally absent — the
        footer shows the always-available, high-frequency keys.
        """
        raw: list[tuple[str, str]] = []
        for binding in self._action_bindings:
            if binding.tip is None:
                continue
            if binding.tip_when is not None and not binding.tip_when(self):
                continue
            for key in resolve_action_keys(binding):
                raw.append((key, binding.tip))
        return merge_footer_pairs(raw)


def collect_overlay_footer_entries(overlay: Component) -> list[tuple[str, str]]:
    """Footer hints for an open modal shell and its inner content.

    Child entries precede shell entries; rows with the same tip are merged.
    """
    parts: list[list[tuple[str, str]]] = []
    child = getattr(overlay, "_child", None)
    if isinstance(child, Component):
        parts.append(child.get_footer_entries())
    parts.append(overlay.get_footer_entries())
    return join_footer_display_pairs(parts)


def bind_signals(
    component: Component,
    *signals: Signal | Computed,
    callback: Callable[[], None] | None = None,
) -> Callable[[], None]:
    """Subscribe component to signals. Returns an unsubscribe function.

    Args:
        component: The component to refresh when signals change.
        *signals: One or more Signal/Computed instances to watch.
        callback: Optional handler. Defaults to component.refresh().

    Returns:
        Unsubscribe function. Caller must store and call on destroy.
    """
    import types

    cb = callback or component.refresh

    def _handler(self: Component, _: object) -> None:
        cb()

    bound = types.MethodType(_handler, component)
    # Keep bound alive as long as component is alive so WeakMethod
    # continues to resolve while the component exists.
    handlers = component._bind_signal_handlers
    handlers.append(bound)

    unsubs: list[Callable[[], None]] = []
    for sig in signals:
        unsubs.append(sig.subscribe(bound))

    def unsubscribe() -> None:
        for unsub in unsubs:
            unsub()
        try:
            handlers.remove(bound)
        except ValueError:
            pass

    return unsubscribe


def resolve_focus_leaf(node: Component) -> Component:
    """Follow ``focus_child``, then drill layout children. Cycle-guarded.

    Does not return a focus-managing parent: a Column with ``focus_index``
    resolves to its focused child, not itself.
    """
    leaf = node
    visited: set[int] = set()
    while True:
        cid = id(leaf)
        if cid in visited:
            _logger.warning(
                "Cycle detected in focus_child chain at %s",
                type(leaf).__name__,
            )
            break
        visited.add(cid)

        child = leaf.focus_child
        if child is not None:
            leaf = child
            continue

        children = leaf.children
        if not children:
            break
        for nested in children:
            if nested.focus_child is not None or nested.children:
                leaf = nested
                break
        else:
            break
    return leaf


def resolve_presentation_leaf(node: Component | None) -> Component | None:
    """Follow ``presentation_child`` while not None. Cycle-guarded."""
    if node is None:
        return None
    seen: set[int] = set()
    while True:
        cid = id(node)
        if cid in seen:
            _logger.warning("Cycle in presentation_child chain")
            break
        seen.add(cid)
        child = node.presentation_child
        if child is None:
            break
        node = child
    return node


def mount_children(component: Component) -> None:
    """Mount every direct child (shared container mount policy)."""
    for child in component.children:
        child.mount()


def unmount_children(component: Component) -> None:
    """Unmount every direct child (shared container unmount policy)."""
    for child in component.children:
        child.unmount()


def is_on_visible_paint_path(component: Component) -> bool:
    """Return True if ``component`` lies under every exclusive ancestor's visible child.

    Ancestors that override :meth:`Component.exclusive_visible_child` paint only
    that child; mounted siblings off the path must not schedule full-tree renders.
    """
    node: Component | None = component
    while node is not None:
        parent = node.parent
        if parent is None:
            return True
        sole = parent.exclusive_visible_child()
        if sole is not None and node is not sole:
            return False
        node = parent
    return True
