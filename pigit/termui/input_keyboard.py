# -*- coding: utf-8 -*-
"""
Module: pigit/termui/input_keyboard.py
Description: Cross-platform semantic keyboard input (timeout read; no termios here).
Author: Zev
Date: 2026-03-26
"""

from __future__ import annotations

import os
import sys
import time
from typing import BinaryIO, Callable, Optional

from pigit.termui import keys
from pigit.termui.geometry import TerminalSize
from pigit.termui.input_trie import match_esc_sequence

_ReadHook = Callable[[float], bytes]


def _utf8_byte_len(first: int) -> int:
    if first < 0x80:
        return 1
    if (first >> 5) == 0b110:
        return 2
    if (first >> 4) == 0b1110:
        return 3
    if (first >> 3) == 0b11110:
        return 4
    return 1


class KeyboardInput:
    """
    Read bytes from stdin (or an injected reader), emit semantic key strings.

    Uses one blocking model: timed read + buffer parse (§4.5). Does not call termios.
    """

    def __init__(
        self,
        stdin: Optional[BinaryIO] = None,
        read_hook: Optional[_ReadHook] = None,
    ) -> None:
        self._stdin = stdin
        self._read_hook = read_hook
        self._buffer = bytearray()
        self._last_size: Optional[TerminalSize] = None

    def _default_stdin(self) -> BinaryIO:
        if self._stdin is not None:
            return self._stdin
        buf = sys.stdin.buffer
        return buf

    def _read_chunk(self, timeout: float) -> bytes:
        if self._read_hook is not None:
            return self._read_hook(timeout)
        if sys.platform == "win32":
            return self._read_chunk_windows(timeout)
        return self._read_chunk_posix(timeout)

    def _read_chunk_posix(self, timeout: float) -> bytes:
        import select

        stdin = self._default_stdin()
        fd = stdin.fileno()
        while True:
            try:
                ready, _, _ = select.select([stdin], [], [], timeout)
                break
            except InterruptedError:
                continue
        if not ready:
            return b""
        try:
            return os.read(fd, 4096)
        except BlockingIOError:
            return b""

    def _read_chunk_windows(self, timeout: float) -> bytes:
        import msvcrt

        deadline = time.monotonic() + timeout
        out = bytearray()
        while time.monotonic() < deadline:
            if msvcrt.kbhit():
                ch = msvcrt.getch()
                if ch in (b"\x00", b"\xe0"):
                    ch += msvcrt.getch()
                out.extend(ch)
                while msvcrt.kbhit():
                    ch2 = msvcrt.getch()
                    if ch2 in (b"\x00", b"\xe0"):
                        ch2 += msvcrt.getch()
                    out.extend(ch2)
                return bytes(out)
            time.sleep(0.001)
        return b""

    def _consume_one(self) -> tuple[Optional[str], int]:
        buf = self._buffer
        if not buf:
            return None, 0

        if sys.platform == "win32":
            if len(buf) >= 2:
                pair = bytes(buf[:2])
                if pair in keys.WIN_EXT_TO_SEMANTIC:
                    sem = keys.WIN_EXT_TO_SEMANTIC[pair]
                    del buf[:2]
                    return sem, 2
            if buf[0] in (0, 0xE0) and len(buf) < 2:
                return None, 0

        b0 = buf[0]

        if b0 == 0x1B:
            sem, n, need_more = match_esc_sequence(bytes(buf))
            if need_more:
                return None, 0
            if n == 0:
                return None, 0
            del buf[:n]
            return sem, n

        if b0 in (9,):
            del buf[:1]
            return keys.KEY_TAB, 1
        if b0 in (10, 13):
            del buf[:1]
            return keys.KEY_ENTER, 1
        if b0 in (8, 127):
            del buf[:1]
            return keys.KEY_BACKSPACE, 1
        if 1 <= b0 <= 26:
            del buf[:1]
            return keys.ctrl_letter_semantic(b0), 1

        if 32 <= b0 <= 126:
            del buf[:1]
            return chr(b0), 1

        if b0 < 0x80:
            del buf[:1]
            return chr(b0), 1

        ln = _utf8_byte_len(b0)
        if len(buf) < ln:
            return None, 0
        chunk = bytes(buf[:ln])
        del buf[:ln]
        try:
            return chunk.decode("utf-8"), ln
        except UnicodeDecodeError:
            return chr(chunk[0]), ln

    def _drain_buffer(self) -> list[str]:
        out: list[str] = []
        while True:
            key, n = self._consume_one()
            if n == 0:
                break
            if key:
                out.append(key)
        return out

    def _resize_events(self) -> list[str]:
        cur = TerminalSize.from_os()
        if self._last_size is None:
            self._last_size = cur
            return []
        if cur != self._last_size:
            self._last_size = cur
            return [keys.KEY_WINDOW_RESIZE]
        return []

    def read_keys(self, timeout: float = 0.1) -> list[str]:
        """
        Block up to ``timeout`` seconds for input, then return semantic keys.

        Appends at most one ``window resize`` when terminal dimensions changed since last call.
        """

        chunk = self._read_chunk(timeout)
        timed_out = chunk == b""
        self._buffer.extend(chunk)
        out = self._drain_buffer()
        if timed_out and self._buffer == bytearray([0x1B]):
            out.append(keys.KEY_ESC)
            self._buffer.clear()
        out.extend(self._resize_events())
        return out
