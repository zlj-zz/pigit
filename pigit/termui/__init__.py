"""
Package: pigit.termui
Description: Unified lightweight terminal UI framework.

Usage:
    from pigit.termui import Component, Toast, ComponentRoot
"""

from __future__ import annotations

# Types and enums
from .types import (
    ActionEventType,
    LayerKind,
    OverlayDispatchResult,
    ToastPosition,
)

# Core components
from ._component import Component, ComponentError, bind_signals, resolve_presented

# Overlay components
from .widgets import (
    AlertDialog,
    AlertDialogBody,
    HelpEntry,
    HelpPanel,
    Popup,
    Sheet,
    Toast,
)

# Event loop
from .event_loop import ExitEventLoop

# Root and application
from ._root import ComponentRoot
from ._application import Application

# Runtime context — single source of truth for all context state
from ._runtime_context import (
    by_id,
    get_registry,
    get_renderer_strict,
    request_render,
)

# Overlay and convenience APIs
from ._overlay_api import (
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
from ._bindings import bind_keys, BindingError, list_bindings
from . import keys
from ._renderer import Renderer
from ._surface import Surface
from ._segment import Segment
from . import palette

from ._syntax import SyntaxTokenizer

__all__ = [
    # Types
    "ActionEventType",
    "LayerKind",
    "OverlayDispatchResult",
    "ToastPosition",
    # Core
    "Component",
    "ComponentError",
    "bind_signals",
    # Overlays
    "AlertDialog",
    "AlertDialogBody",
    "HelpEntry",
    "HelpPanel",
    "Popup",
    "Sheet",
    "Toast",
    # Root & App
    "ComponentRoot",
    "Application",
    "ExitEventLoop",
    # Registry
    "by_id",
    "get_registry",
    # Utils
    "bind_keys",
    "BindingError",
    "list_bindings",
    "keys",
    "Surface",
    "Segment",
    "palette",
    "Renderer",
    "get_renderer_strict",
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
    # Syntax highlighting
    "SyntaxTokenizer",
]
