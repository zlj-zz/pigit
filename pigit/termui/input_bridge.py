# -*- coding: utf-8 -*-
"""
Module: pigit/termui/input_bridge.py
Description: InputTerminal-compatible adapter over KeyboardInput (Session owns termios).
Author: Zev
Date: 2026-03-26
"""

from __future__ import annotations

import math
from typing import Optional

from .input_keyboard import KeyboardInput
from .input_terminal import InputTerminal


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
        """No-op: terminal attributes are owned by Session."""
        return

    def stop(self) -> None:
        """No-op: terminal attributes are owned by Session."""
        return

    def set_input_timeouts(self, timeout: Optional[float]) -> None:
        """Set the keyboard read timeout to a non-negative finite float."""
        if timeout is None:
            return
        t = float(timeout)
        if not math.isfinite(t) or t < 0:
            raise ValueError("timeout must be a non-negative finite float")
        self._timeout = t

    def get_input(
        self, raw_keys: bool = False
    ) -> tuple[list[str], Optional[list[int]]]:
        """Read semantic keys from the keyboard and return them (raw_keys is ignored)."""
        keys = self._kb.read_keys(timeout=self._timeout)
        return (keys, None) if not raw_keys else (keys, None)
