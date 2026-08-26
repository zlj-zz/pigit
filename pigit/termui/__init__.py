"""
Package: pigit.termui
Description: Lightweight terminal UI framework (tiered public API).

Usage:
    from pigit.termui import Application, Component, show_toast, set_theme
    from pigit.termui.widgets import OptionList, Footer, Sheet
    from pigit.termui.containers import Column, TabView
    from pigit.termui.primitives import plain, tokenize_with_positions
"""

from __future__ import annotations

# Types and enums
from .types import (
    EventType,
    EVT_GOTO,
    EVT_SELECTION_CHANGED,
    LayerKind,
    OverlayDispatchResult,
    ToastPosition,
)
from .feedback import FeedbackKind

# Core components
from .component import (
    Component,
    ComponentError,
    bind_signals,
    is_on_visible_paint_path,
    render_child,
    resolve_presentation_leaf,
)

# Event loop
from .event_loop import ExitEventLoop

# Root and application
from .root import ComponentRoot
from .application import Application

# Runtime context — single source of truth for all context state
from ._runtime_context import (
    by_id,
    get_focus_manager,
    get_registry,
    get_renderer,
    get_renderer_strict,
    request_render,
)

# Overlay and convenience APIs
from .overlay import (
    dismiss_sheet,
    dismiss_toast,
    exec_external,
    get_badge,
    get_badge_signal,
    hide_spinner,
    show_badge,
    show_sheet,
    show_spinner,
    show_toast,
)

# Other utilities
from .bindings import (
    Binding,
    bind_action,
    BindingError,
    collect_action_bindings,
    set_key_overrides,
)
from . import keys
from .surface import Surface
from .segment import Segment
from . import palette
from .theme import DEFAULT_THEME, Theme, get_theme, set_theme

from .mouse import MouseButton, MouseEvent, MouseKind
from .async_task import AsyncTask, run_async

__all__ = [
    # Types
    "EventType",
    "EVT_GOTO",
    "EVT_SELECTION_CHANGED",
    "LayerKind",
    "OverlayDispatchResult",
    "ToastPosition",
    "FeedbackKind",
    # Core
    "Component",
    "ComponentError",
    "bind_signals",
    "render_child",
    "resolve_presentation_leaf",
    "is_on_visible_paint_path",
    # Root & App
    "ComponentRoot",
    "Application",
    "ExitEventLoop",
    # Registry
    "by_id",
    "get_registry",
    # Utils
    "bind_action",
    "Binding",
    "collect_action_bindings",
    "set_key_overrides",
    "BindingError",
    "keys",
    "Surface",
    "Segment",
    "palette",
    "Theme",
    "DEFAULT_THEME",
    "get_theme",
    "set_theme",
    "get_renderer",
    "get_renderer_strict",
    "get_focus_manager",
    "MouseButton",
    "MouseEvent",
    "MouseKind",
    "AsyncTask",
    "run_async",
    # Overlay context
    "show_toast",
    "show_sheet",
    "dismiss_sheet",
    "dismiss_toast",
    "show_badge",
    "get_badge",
    "get_badge_signal",
    "show_spinner",
    "hide_spinner",
    "request_render",
    # Session context
    "exec_external",
]
