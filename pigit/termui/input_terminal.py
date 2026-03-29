# -*- coding: utf-8 -*-
"""
Module: pigit/termui/input_terminal.py
Description: Base class for terminal input drivers used by ``AppEventLoop`` and bridges.
Author: Project Team
Date: 2026-03-27
"""

from __future__ import annotations

import os
import sys
from typing import Any, Optional

import termios


class InputTerminal:
    """
    Minimal terminal-input surface for ``tty_signal_keys`` and subclass lifecycle.

    ``TermuiInputBridge`` and custom injected drivers extend this type; ``get_input`` is defined on subclasses.
    """

    def __init__(self) -> None:
        self._signal_keys_set = False
        self._old_signal_keys = None

    def tty_signal_keys(
        self,
        intr: Any = None,
        quit: Any = None,
        start: Any = None,
        stop: Any = None,
        susp: Any = None,
        fileno: Optional[int] = None,
    ) -> Any:
        """
        Read and/or set the tty's signal character settings.
        This function returns the current settings as a tuple.
        Use the string 'undefined' to unmap keys from their signals.
        The value None is used when no change is being made.
        Setting signal keys is done using the integer ascii
        code for the key, eg.  3 for CTRL+C.
        If this function is called after start() has been called
        then the original settings will be restored when stop()
        is called.
        """
        if fileno is None:
            fileno = sys.stdin.fileno()
        if not os.isatty(fileno):
            return

        tattr = termios.tcgetattr(fileno)
        sattr = tattr[6]
        skeys = (
            sattr[termios.VINTR],
            sattr[termios.VQUIT],
            sattr[termios.VSTART],
            sattr[termios.VSTOP],
            sattr[termios.VSUSP],
        )

        if intr == "undefined":
            intr = 0
        if quit == "undefined":
            quit = 0
        if start == "undefined":
            start = 0
        if stop == "undefined":
            stop = 0
        if susp == "undefined":
            susp = 0

        if intr is not None:
            tattr[6][termios.VINTR] = intr
        if quit is not None:
            tattr[6][termios.VQUIT] = quit
        if start is not None:
            tattr[6][termios.VSTART] = start
        if stop is not None:
            tattr[6][termios.VSTOP] = stop
        if susp is not None:
            tattr[6][termios.VSUSP] = susp

        if (
            intr is not None
            or quit is not None
            or start is not None
            or stop is not None
            or susp is not None
        ):
            termios.tcsetattr(fileno, termios.TCSADRAIN, tattr)
            self._signal_keys_set = True

        return skeys
