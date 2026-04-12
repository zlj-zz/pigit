# -*- coding: utf-8 -*-
"""
Module: pigit/termui/tty_io.py
Description: Low-level TTY helpers for picker scenes (cbreak reads, escape sequences, viewport math).
Author: Zev
Date: 2026-03-27
"""

from __future__ import annotations

import shutil
import sys
import time
from contextlib import contextmanager
from typing import Callable, List, Optional, Tuple

# Raw stdin bytes this module recognizes (see also inline comments at each ``if``):
#   \x1b (27)     ESC — starts ANSI/ECMA-48 escapes (CSI ``ESC [``, SS3 ``ESC O``, etc.).
#   \x03 (3)      ETX — Ctrl+C; turned into KeyboardInterrupt.
#   \x08 (8) BS   Backspace; \x7f (127) DEL — often Backspace on Unix TTYs.
#   0x40–0x7E     Inclusive range of the final byte of a CSI/SS3 sequence (``@`` through ``~``).
#   \x00 / \xe0   Windows ``msvcrt``: extended-key prefix; \xe0\x53 is often Delete.

MIN_LIST_ROWS = 1


@contextmanager
def _posix_cbreak(fd: int):
    """Keep stdin in cbreak for the duration of a multi-key read."""
    import termios
    import tty

    old = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)
        yield
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def read_char_raw() -> str:
    """Read one byte/char from stdin in cbreak/raw mode (POSIX) or msvcrt (Windows)."""
    if sys.platform == "win32":
        import msvcrt

        ch = msvcrt.getch()
        # Extended keys: 0x00 / 0xe0 prefix + second scancode byte.
        if ch in (b"\x00", b"\xe0"):
            ch += msvcrt.getch()
        c = ch.decode("latin-1", errors="replace")
        if c == "\x03":  # Ctrl+C (ETX)
            raise KeyboardInterrupt
        return c

    import termios
    import tty

    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)
        c = sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
    if c == "\x03":  # Ctrl+C (ETX)
        raise KeyboardInterrupt
    return c


def _consume_csi_from_stdin() -> None:
    """Consume the rest of a CSI / SS3 sequence (caller already read ``ESC [`` or similar)."""
    while True:
        c = sys.stdin.read(1)
        if not c:
            break
        # CSI ends with a byte in 0x40–0x7E (final character of the sequence).
        if 0x40 <= ord(c) <= 0x7E:
            break


def _after_esc_posix() -> Optional[str]:
    """
    Handle byte read after ESC on POSIX. Return None if user cancelled (lone ESC).

    Returns:
        None: lone ESC (cancel).
        "": consumed an escape sequence (arrow keys etc.); no character for buffer.
        str length 1: next data character to append to the line buffer.
    """
    import select

    fd = sys.stdin.fileno()
    ready, _, _ = select.select([sys.stdin], [], [], 0.05)
    if not ready:
        return None
    c2 = sys.stdin.read(1)
    if c2 == "[":  # CSI
        _consume_csi_from_stdin()
        return ""
    if c2 == "O":
        ck = sys.stdin.read(1)
        # SS3 final byte (same 0x40–0x7E rule as CSI).
        if ck and 0x40 <= ord(ck) <= 0x7E:
            return ""
        return ck or ""
    return c2


def _after_esc_windows() -> Optional[str]:
    """Same contract as :func:`_after_esc_posix` using ``msvcrt``."""
    import msvcrt

    deadline = time.monotonic() + 0.05
    while time.monotonic() < deadline:
        if msvcrt.kbhit():
            ch2 = msvcrt.getch()
            if ch2 == b"[":
                while True:
                    ck = msvcrt.getch()
                    if ck and 0x40 <= ord(ck) <= 0x7E:  # CSI final byte
                        break
                return ""
            return ch2.decode("latin-1", errors="replace")
        time.sleep(0.001)
    return None


def lone_esc_or_consume_sequence() -> bool:
    """
    After ``read_char`` returned ESC (outside raw line mode).

    Returns:
        True if this was a lone ESC (quit / cancel at current UI level).
        False if an escape sequence (e.g. arrow keys) was consumed instead.
    """
    if sys.platform == "win32":
        return _after_esc_windows() is None

    import select

    fd = sys.stdin.fileno()
    ready, _, _ = select.select([sys.stdin], [], [], 0.05)
    if not ready:
        return True
    c2 = sys.stdin.read(1)
    if c2 == "[":  # CSI: ESC [ …
        _consume_csi_from_stdin()
        return False
    if c2 == "O":
        ck = sys.stdin.read(1)
        if ck and 0x40 <= ord(ck) <= 0x7E:  # SS3 final byte
            return False
        return False
    return False


def _echo_erase_last_char(
    write: Callable[[str], None], flush: Callable[[], None]
) -> None:
    """Erase one character on the terminal (cursor-at-end line editing)."""
    write("\b \b")
    flush()


def _posix_handle_esc_in_line(
    write: Callable[[str], None],
    flush: Callable[[], None],
    buf: List[str],
) -> bool:
    """
    Handle the byte after ``ESC`` during raw line read.

    Returns:
        False if the user cancelled with a lone ESC.
        True if the sequence was consumed or a character was appended.
    """
    import select

    fd = sys.stdin.fileno()
    ready, _, _ = select.select([sys.stdin], [], [], 0.05)
    if not ready:
        return False
    c2 = sys.stdin.read(1)
    if not c2:
        return True
    if c2 == "[":  # CSI
        parts: List[str] = []
        while True:
            ck = sys.stdin.read(1)
            if not ck:
                return True
            parts.append(ck)
            if 0x40 <= ord(ck) <= 0x7E:  # CSI final byte
                break
        seq = "".join(parts)
        # xterm-style Delete: ESC [ 3 ~ (params + ``~`` terminator).
        if seq == "3~":
            if buf:
                buf.pop()
                _echo_erase_last_char(write, flush)
            return True
        return True
    if c2 == "O":
        ck = sys.stdin.read(1)
        if ck and 0x40 <= ord(ck) <= 0x7E:  # SS3 final byte (e.g. F-keys)
            return True
        if ck:
            write(ck)
            flush()
            buf.append(ck)
        return True
    write(c2)
    flush()
    buf.append(c2)
    return True


def read_line_cancellable(
    *,
    write: Callable[[str], None],
    flush: Callable[[], None],
    prompt: str,
) -> Optional[str]:
    """
    Read a line with echo, **Backspace** / **Delete** removing the last character,
    **Enter** to commit, **ESC** alone to cancel (returns ``None``).

    **Ctrl+C** raises :exc:`KeyboardInterrupt`.

    Returns:
        The line without trailing newline, or ``None`` if the user cancelled with ESC.
    """
    write(prompt)
    flush()
    buf: List[str] = []

    if sys.platform == "win32":
        import msvcrt

        while True:
            chb = msvcrt.getch()
            if chb == b"\x03":  # Ctrl+C
                raise KeyboardInterrupt
            if chb in (b"\r", b"\n"):
                write("\n")
                flush()
                return "".join(buf)
            if chb in (b"\x00", b"\xe0"):
                chb2 = msvcrt.getch()
                # Delete on many Windows consoles: extended prefix + 0x53.
                if chb == b"\xe0" and chb2 == b"\x53":
                    if buf:
                        buf.pop()
                        _echo_erase_last_char(write, flush)
                    continue
                continue
            if chb == b"\x1b":  # ESC — may start escape or Alt+char
                follow = _after_esc_windows()
                if follow is None:
                    return None
                if follow:
                    write(follow)
                    flush()
                    buf.append(follow)
                continue
            if chb in (b"\x7f", b"\x08"):  # DEL / BS — backspace
                if buf:
                    buf.pop()
                    _echo_erase_last_char(write, flush)
                continue
            s = chb.decode("latin-1", errors="replace")
            write(s)
            flush()
            buf.append(s)

    fd = sys.stdin.fileno()
    with _posix_cbreak(fd):
        while True:
            c = sys.stdin.read(1)
            if not c:
                return "".join(buf)
            if c == "\x03":  # Ctrl+C (ETX)
                raise KeyboardInterrupt
            if c in ("\r", "\n"):
                write("\n")
                flush()
                return "".join(buf)
            if (
                c == "\x1b"
            ):  # ESC — lone vs CSI/SS3 handled in _posix_handle_esc_in_line
                if not _posix_handle_esc_in_line(write, flush, buf):
                    return None
                continue
            if c in ("\x7f", "\x08"):  # DEL / BS — backspace
                if buf:
                    buf.pop()
                    _echo_erase_last_char(write, flush)
                continue
            write(c)
            flush()
            buf.append(c)


def tty_ok() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def terminal_size() -> Tuple[int, int]:
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
    if len(one) <= max_cols:
        return one
    if max_cols <= 1:
        return one[:max_cols]
    return one[: max_cols - 1] + "…"
