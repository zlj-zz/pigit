# -*- coding: utf-8 -*-
"""
Module: pigit/termui/session.py
Description: Terminal session — cbreak/raw only here; alternate screen and cursor.
Author: Zev
Date: 2026-03-26
"""

from __future__ import annotations

import sys
from types import TracebackType
from typing import Optional, TextIO, Type

from ._renderer import Renderer


class Session:
    """
    Enter and restore terminal state (POSIX termios; optional alternate screen).

    KeyboardInput must not call termios; this class owns terminal attributes on POSIX.
    """

    def __init__(self, alt_screen: bool = False, stdin: Optional[TextIO] = None, stdout: Optional[TextIO] = None):
        self.alt_screen = alt_screen
        self.stdin = stdin or sys.stdin
        self.stdout = stdout or sys.stdout
        self._fd = self.stdin.fileno()
        self._old_termios: Optional[list] = None
        self.renderer = Renderer(self)

    def __enter__(self) -> "Session":
        if not self.stdin.isatty() or not self.stdout.isatty():
            raise RuntimeError("A TTY is required for interactive terminal mode.")
        if sys.platform != "win32":
            import termios
            import tty

            self._old_termios = termios.tcgetattr(self._fd)
            tty.setcbreak(self._fd)
        if self.alt_screen:
            self.stdout.write("\033[?1049h\033[?25l")
        else:
            self.stdout.write("\033[?25l")
        self.stdout.flush()
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        try:
            if self.alt_screen:
                self.stdout.write("\033[?1049l")
            self.stdout.write("\033[?25h")
            self.stdout.flush()
        finally:
            if sys.platform != "win32" and self._old_termios is not None:
                import termios

                termios.tcsetattr(self._fd, termios.TCSADRAIN, self._old_termios)
