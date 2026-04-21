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
    ActionLiteral,
    LayerKind,
    OverlayDispatchResult,
    OverlaySurface,
    SurfaceProtocol,
    ToastPosition,
)

# Core components
from pigit.termui._component_base import Component, ComponentError
from pigit.termui._component_mixins import (
    GitPanelLazyResizeMixin,
    OverlayClientMixin,
)
from pigit.termui._component_layouts import Column, TabView
from pigit.termui._component_widgets import (
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

# Other utilities
from pigit.termui._bindings import bind_keys, list_bindings
from pigit.termui._geometry import TerminalSize
from pigit.termui._renderer import Renderer
from pigit.termui._renderer_context import get_renderer_strict
from pigit.termui._surface import Surface

# Picker
from pigit.termui._picker import PickerRow

__all__ = [
    # Types
    "ActionLiteral",
    "LayerKind",
    "OverlayDispatchResult",
    "OverlaySurface",
    "SurfaceProtocol",
    "ToastPosition",
    # Core
    "Component",
    "ComponentError",
    "OverlayClientMixin",
    "GitPanelLazyResizeMixin",
    # Containers
    "TabView",
    # Widgets
    "Column",
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
    "list_bindings",
    "Surface",
    "Renderer",
    "get_renderer_strict",
    "TerminalSize",
    # Picker
    "PickerRow",
]
