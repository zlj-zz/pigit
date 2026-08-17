"""
Module: pigit/termui/tty_io.py
Description: Low-level TTY helpers for picker scenes (cbreak reads, escape sequences, viewport math).
Author: Zev
Date: 2026-03-27
"""

from __future__ import annotations

import shutil
import sys

from .wcwidth_table import truncate_by_width, wcswidth

# Raw stdin bytes this module recognizes (see also inline comments at each ``if``):
#   \x1b (27)     ESC — starts ANSI/ECMA-48 escapes (CSI ``ESC [``, SS3 ``ESC O``, etc.).
#   \x03 (3)      ETX — Ctrl+C; turned into KeyboardInterrupt.
#   \x08 (8) BS   Backspace; \x7f (127) DEL — often Backspace on Unix TTYs.
#   0x40–0x7E     Inclusive range of the final byte of a CSI/SS3 sequence (``@`` through ``~``).

MIN_LIST_ROWS = 1

SUPPORTED_SYSTEMS = "macOS, Linux"

UNSUPPORTED_PLATFORM_MSG = (
    f"@red(Pigit TUI) is not supported on Windows. "
    f"Supported systems: {SUPPORTED_SYSTEMS}."
)


def platform_supported() -> bool:
    """Return True if the current OS supports the TUI.

    Uses ``sys.platform != "win32"`` because the TUI relies on ``termios``,
    present on every non-Windows CPython. Deliberately independent of
    ``const.IS_WIN`` (which picks the home path and is an app-level concern).
    """
    return sys.platform != "win32"


def tty_ok() -> bool:
    """Return True if both stdin and stdout are connected to a TTY."""
    return sys.stdin.isatty() and sys.stdout.isatty()


def terminal_size() -> tuple[int, int]:
    """Return (columns, rows). Fallback if ioctl fails."""
    try:
        sz = shutil.get_terminal_size()
        return max(20, sz.columns), max(1, sz.lines)
    except OSError:
        return 80, 24


def truncate_line(text: str, max_cols: int) -> str:
    """One physical line for the picker; strip newlines and trim to width."""
    one = " ".join(text.split())
    if max_cols <= 0:
        return ""
    one_width = wcswidth(one)
    if one_width <= max_cols:
        return one
    if max_cols <= 1:
        return truncate_by_width(one, max_cols)
    return truncate_by_width(one, max_cols - 1) + "…"
