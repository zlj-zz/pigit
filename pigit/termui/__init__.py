# -*- coding: utf-8 -*-
"""
Package: pigit.termui
Description: Unified lightweight terminal UI (keyboard semantics, session, renderer).
Author: Project Team
Date: 2026-03-26
"""

from __future__ import annotations

from pigit.termui.component import Component
from pigit.termui.geometry import TerminalSize
from pigit.termui.input_keyboard import KeyboardInput
from pigit.termui.loop import run_key_echo
from pigit.termui.render import Renderer
from pigit.termui.session import Session
from pigit.termui.text import get_width, plain

from . import keys

__all__ = [
    "Component",
    "KeyboardInput",
    "Renderer",
    "Session",
    "TerminalSize",
    "get_width",
    "keys",
    "plain",
    "run_key_echo",
]
