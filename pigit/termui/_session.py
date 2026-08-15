"""
Module: pigit/termui/session.py
Description: Terminal session — cbreak/raw only here; alternate screen and cursor.
Author: Zev
Date: 2026-03-26
"""

from __future__ import annotations

import sys
from types import TracebackType
from typing import TextIO

from ._renderer import Renderer

# xterm mouse reporting: button-event tracking (1002) + SGR extended
# coordinates (1006). Enabled on POSIX terminals.
_MOUSE_ENABLE = "\033[?1002h\033[?1006h"
_MOUSE_DISABLE = "\033[?1002l\033[?1006l"


class Session:
    """
    Enter and restore terminal state (termios; optional alternate screen).

    KeyboardInput must not call termios; this class owns terminal attributes.
    """

    def __init__(
        self,
        alt_screen: bool = False,
        stdin: TextIO | None = None,
        stdout: TextIO | None = None,
    ):
        self.alt_screen = alt_screen
        self.stdin = stdin or sys.stdin
        self.stdout = stdout or sys.stdout
        self._fd = self.stdin.fileno()
        self._old_termios: list | None = None
        self.renderer = Renderer(self)

    def __enter__(self) -> Session:
        if not self.stdin.isatty() or not self.stdout.isatty():
            raise RuntimeError("A TTY is required for interactive terminal mode.")
        self._suspended = False
        import termios
        import tty

        self._old_termios = termios.tcgetattr(self._fd)
        tty.setcbreak(self._fd)
        if self.alt_screen:
            self.stdout.write("\033[?1049h\033[?25l")
        else:
            self.stdout.write("\033[?25l")
        self.stdout.write(_MOUSE_ENABLE)
        self.stdout.flush()
        return self

    def suspend(self) -> None:
        """Temporarily restore terminal to normal state for external full-screen processes.

        Idempotent: skips if already suspended.
        """
        if getattr(self, "_suspended", False):
            return
        self._suspended = True
        self.stdout.write(_MOUSE_DISABLE)
        if self.alt_screen:
            self.stdout.write("\033[?1049l")
        self.stdout.write("\033[?25h")
        self.stdout.flush()
        if self._old_termios is not None:
            import termios

            termios.tcsetattr(self._fd, termios.TCSADRAIN, self._old_termios)

    def resume(self) -> None:
        """Restore terminal back to TUI mode from normal state.

        Idempotent: skips if not currently suspended.
        """
        if not getattr(self, "_suspended", False):
            return
        self._suspended = False
        import termios
        import tty

        tty.setcbreak(self._fd)
        # External full-screen programs (e.g. vim/nvim) may leave focus
        # events, color reports, or other escape sequences in the input
        # buffer after they exit. Flushing the buffer before resuming the
        # TUI prevents those bytes from leaking to KeyboardInput and being
        # misinterpreted as user keystrokes (e.g. ';' opening the palette).
        termios.tcflush(self._fd, termios.TCIFLUSH)
        if self.alt_screen:
            self.stdout.write("\033[?1049h")
        self.stdout.write("\033[?25l")
        self.stdout.write(_MOUSE_ENABLE)
        self.stdout.flush()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        try:
            self.stdout.write(_MOUSE_DISABLE)
            if self.alt_screen:
                self.stdout.write("\033[?1049l")
            self.stdout.write("\033[?25h")
            self.stdout.flush()
        finally:
            if self._old_termios is not None:
                import termios

                termios.tcsetattr(self._fd, termios.TCSADRAIN, self._old_termios)
