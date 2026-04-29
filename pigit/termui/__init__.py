# -*- coding: utf-8 -*-
"""
Package: pigit.termui
Description: Unified lightweight terminal UI framework.

Usage:
    from pigit.termui import Component, Toast, ComponentRoot
"""

from __future__ import annotations

# Types and enums
from pigit.termui.types import (
    ActionEventType,
    LayerKind,
    OverlayDispatchResult,
    OverlaySurface,
    SurfaceProtocol,
    ToastPosition,
)

# Core components
from pigit.termui._component_base import Component, ComponentError
from pigit.termui._component_layouts import Column, Row, TabView
from pigit.termui._component_widgets import (
    Header,
    InputLine,
    ItemSelector,
    LineTextBrowser,
    StatusBar,
)
from pigit.termui._reactive import Computed, Signal

# Overlay components
from pigit.termui._overlay_components import (
    AlertDialog,
    AlertDialogBody,
    HelpEntry,
    HelpPanel,
    Popup,
    Sheet,
    Toast,
)

# Event loop
from pigit.termui.event_loop import ExitEventLoop

# Root and application
from pigit.termui._root import ComponentRoot
from pigit.termui._application import Application

# Overlay context (module-level functions)
from pigit.termui._overlay_context import (
    dismiss_sheet,
    get_badge,
    hide_spinner,
    show_badge,
    show_spinner,
    show_toast,
    show_sheet,
)
from pigit.termui._session_context import exec_external

# Other utilities
from pigit.termui._bindings import bind_keys, BindingError, list_bindings
from pigit.termui import keys
from pigit.termui._geometry import TerminalSize
from pigit.termui._color import ColorAdapter, ColorMode
from pigit.termui._renderer import Renderer
from pigit.termui._renderer_context import get_renderer_strict
from pigit.termui._surface import Cell, FlatCell, Surface
from pigit.termui import palette

# Picker
from pigit.termui._picker import PickerRow
from pigit.termui._syntax import SyntaxTokenizer
from pigit.termui._text import plain

__all__ = [
    # Types
    "ActionEventType",
    "LayerKind",
    "OverlayDispatchResult",
    "OverlaySurface",
    "SurfaceProtocol",
    "ToastPosition",
    # Core
    "Component",
    "ComponentError",
    # Containers
    "TabView",
    "Column",
    "Row",
    # Widgets
    "Header",
    "InputLine",
    "ItemSelector",
    "LineTextBrowser",
    "StatusBar",
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
    # Reactive
    "Computed",
    "Signal",
    # Utils
    "bind_keys",
    "BindingError",
    "list_bindings",
    "keys",
    "Surface",
    "FlatCell",
    "Cell",
    "palette",
    "ColorAdapter",
    "ColorMode",
    "Renderer",
    "get_renderer_strict",
    "TerminalSize",
    # Overlay context
    "show_toast",
    "show_sheet",
    "dismiss_sheet",
    "show_badge",
    "get_badge",
    "show_spinner",
    "hide_spinner",
    # Session context
    "exec_external",
    # Syntax highlighting
    "SyntaxTokenizer",
    "plain",
    # Picker
    "PickerRow",
]
