# -*- coding: utf-8 -*-
"""
Package: pigit.termui
Description: Unified lightweight terminal UI (keyboard semantics, session, renderer).
Author: Zev
Date: 2026-03-26
"""

from __future__ import annotations

from pigit.termui.bindings import BindingError, bind_keys, list_bindings
from pigit.termui.application import Application
from pigit.termui.components import (
    ActionLiteral,
    Component,
    GitPanelLazyResizeMixin,
    ItemSelector,
    LayoutContainer,
    LineTextBrowser,
    TabView,
)
from pigit.termui.components_overlay import AlertDialog, HelpPanel, HelpEntry, Popup
from pigit.termui.event_loop import AppEventLoop, ExitEventLoop
from pigit.termui.overlay_host import OverlayHostMixin
from pigit.termui.overlay_kinds import (
    OverlayDispatchResult,
    OverlayKind,
    OverlaySurface,
)
from pigit.termui.geometry import TerminalSize
from pigit.termui.input_keyboard import KeyboardInput
from pigit.termui.key_echo import run_key_echo
from pigit.termui.render import Renderer
from pigit.termui.session import Session
from pigit.termui.text import get_width, plain, sanitize_for_display

from . import keys

__all__ = [
    "ActionLiteral",
    "AlertDialog",
    "AppEventLoop",
    "Application",
    "BindingError",
    "Component",
    "ExitEventLoop",
    "GitPanelLazyResizeMixin",
    "HelpEntry",
    "HelpPanel",
    "ItemSelector",
    "KeyboardInput",
    "LayoutContainer",
    "LineTextBrowser",
    "OverlayDispatchResult",
    "OverlayHostMixin",
    "OverlayKind",
    "OverlaySurface",
    "Popup",
    "Renderer",
    "Session",
    "TabView",
    "TerminalSize",
    "bind_keys",
    "get_width",
    "keys",
    "list_bindings",
    "plain",
    "run_key_echo",
    "sanitize_for_display",
]
