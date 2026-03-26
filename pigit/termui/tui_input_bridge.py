# -*- coding: utf-8 -*-
"""
Module: pigit/termui/tui_input_bridge.py
Description: InputTerminal-compatible adapter over KeyboardInput (Session owns termios).
Author: Project Team
Date: 2026-03-26
"""

from __future__ import annotations

from typing import List, Optional, Tuple

from pigit.tui.input import InputTerminal

from pigit.termui.input_keyboard import KeyboardInput


class TermuiInputBridge(InputTerminal):
    """
    Feed :class:`KeyboardInput` semantic keys into the legacy ``EventLoop`` / ``get_input`` API.

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
        if timeout is not None:
            self._timeout = float(timeout)

    def get_input(
        self, raw_keys: bool = False
    ) -> Tuple[List[str], Optional[List[int]]]:
        keys = self._kb.read_keys(timeout=self._timeout)
        return (keys, None) if not raw_keys else (keys, None)
