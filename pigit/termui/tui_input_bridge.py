# -*- coding: utf-8 -*-
"""
Module: pigit/termui/tui_input_bridge.py
Description: InputTerminal-compatible adapter over KeyboardInput (Session owns termios).
Author: Zev
Date: 2026-03-26
"""

from __future__ import annotations

import math
from typing import Optional

from pigit.termui.input_keyboard import KeyboardInput
from pigit.termui.input_terminal import InputTerminal


class TermuiInputBridge(InputTerminal):
    """
    Feed :class:`KeyboardInput` semantic keys into :class:`~pigit.termui.event_loop.AppEventLoop` / ``get_input`` API.

    ``start()`` / ``stop()`` are no-ops: terminal attributes are owned by :class:`pigit.termui.session.Session`.
    """

    def __init__(self) -> None:
        super().__init__()
        self._kb = KeyboardInput()
        self._timeout = 0.125

    def start(self) -> None:
        return

    def stop(self) -> None:
        return

    def set_input_timeouts(self, timeout: Optional[float]) -> None:
        if timeout is None:
            return
        t = float(timeout)
        if not math.isfinite(t) or t < 0:
            raise ValueError("timeout must be a non-negative finite float")
        self._timeout = t

    def get_input(
        self, raw_keys: bool = False
    ) -> tuple[list[str], Optional[list[int]]]:
        keys = self._kb.read_keys(timeout=self._timeout)
        return (keys, None) if not raw_keys else (keys, None)
