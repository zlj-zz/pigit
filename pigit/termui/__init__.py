# -*- coding: utf-8 -*-
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
    OverlaySurface,
    SurfaceProtocol,
    ToastPosition,
)

# Core components
from ._component_base import Component, ComponentError, bind_signals
from ._component_layouts import Column, Row, TabView
from ._component_graph import HeatmapGrid, StepLineChart
from ._component_widgets import (
    Header,
    InputLine,
    ItemSelector,
    LineTextBrowser,
    StatusBar,
)
from ._reactive import Computed, Signal, ValueRef

# Overlay components
from ._overlay_components import (
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

# Overlay context (module-level functions)
from ._overlay_context import (
    dismiss_sheet,
    get_badge,
    get_badge_signal,
    hide_spinner,
    show_badge,
    show_spinner,
    show_toast,
    show_sheet,
)
from ._session_context import exec_external

# Other utilities
from ._bindings import bind_keys, BindingError, list_bindings
from . import keys
from ._geometry import TerminalSize
from ._color import ColorAdapter, ColorMode
from ._renderer import Renderer
from ._renderer_context import get_renderer_strict
from ._surface import Cell, FlatCell, Surface
from ._segment import Segment
from . import palette

# Registry
from ._component_registry import by_id, get_registry

# Picker
from ._picker import PickerRow
from ._syntax import SyntaxTokenizer
from ._text import plain

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
    "bind_signals",
    # Containers
    "TabView",
    "Column",
    "Row",
    # Widgets
    "Header",
    "HeatmapGrid",
    "InputLine",
    "StepLineChart",
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
    # Registry
    "by_id",
    "get_registry",
    # Reactive
    "Computed",
    "Signal",
    "ValueRef",
    # Utils
    "bind_keys",
    "BindingError",
    "list_bindings",
    "keys",
    "Surface",
    "FlatCell",
    "Cell",
    "Segment",
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
    "get_badge_signal",
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
