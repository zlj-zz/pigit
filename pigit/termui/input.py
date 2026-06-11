"""
Module: pigit/termui/input.py
Description: Terminal input layer — keyboard reader, escape-sequence matcher,
    input-terminal base class, and the bridge used by the event loop.
Author: Zev
Date: 2026-05-18
"""

from __future__ import annotations

import logging
import os
import queue
import sys
import threading
import time
from typing import Any, BinaryIO
from collections.abc import Callable

from shutil import get_terminal_size

from . import keys

_logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Escape-sequence trie (formerly input_trie.py)
# ---------------------------------------------------------------------------


def _csi_or_ss3_byte_count(buf: bytes) -> int:
    """
    If buf starts a CSI or SS3 sequence, return total length when the final byte is present.

    Returns:
        0 if incomplete or not a CSI/SS3 leader after ESC.
    """

    if len(buf) < 2 or buf[0] != 0x1B:
        return 0
    if buf[1] == ord("["):
        for i in range(2, len(buf)):
            if 0x40 <= buf[i] <= 0x7E:
                return i + 1
        return 0
    if buf[1] == ord("O"):
        if len(buf) < 3:
            return 0
        if 0x40 <= buf[2] <= 0x7E:
            return 3
        return 0
    return 0


def _parse_csi_27(chunk: bytes) -> str | None:
    """Parse xterm modifyOtherKeys sequence \x1b[27;<mod>;<key>~."""
    if not chunk.startswith(b"\x1b[") or chunk[-1:] != b"~":
        return None
    inner = chunk[2:-1].decode("ascii", errors="ignore")
    if not inner.startswith("27;"):
        return None
    parts = inner.split(";")
    if len(parts) != 3:
        return None
    try:
        modifier = int(parts[1])
        key_code = int(parts[2])
    except ValueError:
        return None
    if key_code == 13:
        if modifier == 2:
            return keys.KEY_SHIFT_ENTER
        if modifier == 5:
            return keys.KEY_CTRL_ENTER
        if modifier == 6:
            return keys.KEY_CTRL_SHIFT_ENTER
    return None


def _parse_csi_u(chunk: bytes) -> str | None:
    """Parse CSI-u sequence \x1b[<code>;<mod>u -> semantic key string.

    Also handles the kitty extended format \x1b[<code>;<mod>:<event>u.

    Modifier mask: 1=none 2=shift 3=alt 4=shift+alt 5=ctrl 6=ctrl+shift
    7=ctrl+alt 8=ctrl+shift+alt
    """
    if not chunk.startswith(b"\x1b[") or chunk[-1:] != b"u":
        return None
    params = chunk[2:-1].decode("ascii", errors="ignore").split(";")
    if not params:
        return None
    try:
        key_code = int(params[0])
    except ValueError:
        return None
    modifier_str = params[1].split(":")[0] if len(params) > 1 else "1"
    try:
        modifier = int(modifier_str)
    except ValueError:
        modifier = 1
    # Enter (code 13)
    if key_code == 13:
        if modifier == 2:
            return keys.KEY_SHIFT_ENTER
        if modifier == 5:
            return keys.KEY_CTRL_ENTER
        if modifier == 6:
            return keys.KEY_CTRL_SHIFT_ENTER
    return None


def match_esc_sequence(buf: bytes) -> tuple[str | None, int, bool]:
    """
    Match a leading escape sequence.

    Returns:
        (semantic, consumed_bytes, need_more_input)
    """

    if not buf or buf[0] != 0x1B:
        return None, 0, False
    if len(buf) == 1:
        return None, 0, True

    for seq, sem in keys.iter_esc_sequences_longest_first():
        if buf.startswith(seq):
            return sem, len(seq), False

    for seq, _ in keys.iter_esc_sequences_longest_first():
        if len(buf) < len(seq) and seq.startswith(buf):
            return None, 0, True

    if buf.startswith(b"\x1b[") or buf.startswith(b"\x1bO"):
        n = _csi_or_ss3_byte_count(buf)
        if n == 0:
            return None, 0, True
        chunk = buf[:n]
        if chunk in keys.ESC_TO_SEMANTIC:
            return keys.ESC_TO_SEMANTIC[chunk], n, False
        csi_u = _parse_csi_u(chunk)
        if csi_u:
            return csi_u, n, False
        csi_27 = _parse_csi_27(chunk)
        if csi_27:
            return csi_27, n, False
        return None, n, False

    # ESC + non-CSI: emit ESC; caller may re-parse following bytes.
    return keys.KEY_ESC, 1, False


# ---------------------------------------------------------------------------
# Keyboard input (formerly input_keyboard.py)
# ---------------------------------------------------------------------------

_ReadHook = Callable[[float | None], bytes]


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

    Uses one blocking model: timed read + buffer parse. Does not call termios.
    """

    def __init__(
        self,
        stdin: BinaryIO | None = None,
        read_hook: _ReadHook | None = None,
    ) -> None:
        self._stdin = stdin
        self._read_hook = read_hook
        self._buffer = bytearray()
        self._last_size: tuple[int, int] | None = None
        self._queue: queue.Queue[str] = queue.Queue()
        self._thread: threading.Thread | None = None
        self._running = False

    def _default_stdin(self) -> BinaryIO:
        if self._stdin is not None:
            return self._stdin
        buf = sys.stdin.buffer
        return buf

    def _read_chunk(self, timeout: float | None) -> bytes:
        if self._read_hook is not None:
            return self._read_hook(timeout)
        if sys.platform == "win32":
            return self._read_chunk_windows(timeout)
        return self._read_chunk_posix(timeout)

    def _read_chunk_posix(self, timeout: float | None) -> bytes:
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

    def _read_chunk_windows(self, timeout: float | None) -> bytes:
        import msvcrt

        _msvcrt: Any = msvcrt
        if timeout is None:
            # Blocking indefinitely: msvcrt has no true blocking read with
            # interrupt support, so we poll at 20 Hz (lower CPU than 1 kHz).
            out = bytearray()
            while True:
                if _msvcrt.kbhit():
                    ch = _msvcrt.getch()
                    if ch in (b"\x00", b"\xe0"):
                        ch += _msvcrt.getch()
                    out.extend(ch)
                    while _msvcrt.kbhit():
                        ch2 = _msvcrt.getch()
                        if ch2 in (b"\x00", b"\xe0"):
                            ch2 += _msvcrt.getch()
                        out.extend(ch2)
                    return bytes(out)
                time.sleep(0.05)
        deadline = time.monotonic() + timeout
        out = bytearray()
        while time.monotonic() < deadline:
            if _msvcrt.kbhit():
                ch = _msvcrt.getch()
                if ch in (b"\x00", b"\xe0"):
                    ch += _msvcrt.getch()
                out.extend(ch)
                while _msvcrt.kbhit():
                    ch2 = _msvcrt.getch()
                    if ch2 in (b"\x00", b"\xe0"):
                        ch2 += _msvcrt.getch()
                    out.extend(ch2)
                return bytes(out)
            time.sleep(0.001)
        return b""

    def _consume_one(self) -> tuple[str | None, int]:
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
        sz = get_terminal_size()
        cur = (sz.columns, sz.lines)
        if self._last_size is None:
            self._last_size = cur
            return []
        if cur != self._last_size:
            self._last_size = cur
            return [keys.KEY_WINDOW_RESIZE]
        return []

    def read_keys(self, timeout: float | None = 0.1) -> list[str]:
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

    def start(self) -> None:
        """Start the keyboard reader thread."""
        self._running = True
        self._thread = threading.Thread(target=self._read_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop the keyboard reader thread."""
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=0.125)
            self._thread = None

    def get_key(self) -> str | None:
        """Non-blocking fetch of one key. Returns None if none available."""
        try:
            return self._queue.get_nowait()
        except queue.Empty:
            return None

    def _read_loop(self) -> None:
        """Background thread: blocking read from stdin, parse and enqueue."""
        while self._running:
            # Fixed short timeout so we wait for ESC continuation bytes but
            # also poll _running regularly, preventing indefinite blocking
            # during stop().
            timeout = 0.125
            try:
                keys = self.read_keys(timeout=timeout)
            except Exception:
                _logger.exception("Keyboard input read failed")
                time.sleep(0.1)
                continue
            for key in keys:
                self._queue.put(key)


# ---------------------------------------------------------------------------
# Input-terminal base (formerly input_terminal.py)
# ---------------------------------------------------------------------------

import termios


class InputTerminal:
    """
    Minimal terminal-input surface for ``tty_signal_keys`` and subclass lifecycle.

    ``TermuiInputBridge`` and custom injected drivers extend this type;
    ``get_input`` is defined on subclasses.
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
        fileno: int | None = None,
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
        assert fileno is not None
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

    def start(self) -> None:
        """Start the input reader. No-op by default; override in subclasses."""
        return

    def stop(self) -> None:
        """Stop the input reader. No-op by default; override in subclasses."""
        return

    def get_key(self) -> str | None:
        """Non-blocking read of a single semantic key. Must be overridden in subclasses."""
        raise NotImplementedError("Subclasses must implement get_key()")

    def get_input(self, raw_keys: bool = False) -> tuple[list[str], list[int] | None]:
        """Read semantic keys from the input source. Must be overridden in subclasses."""
        raise NotImplementedError("Subclasses must implement get_input()")


# ---------------------------------------------------------------------------
# Bridge (formerly input_bridge.py)
# ---------------------------------------------------------------------------


class TermuiInputBridge(InputTerminal):
    """
    Feed :class:`KeyboardInput` semantic keys into
    :class:`~pigit.termui.event_loop.AppEventLoop` / ``get_input`` API.

    ``start()`` / ``stop()`` are no-ops: terminal attributes are owned by
    :class:`~pigit.termui._session.Session`.
    """

    def __init__(self) -> None:
        super().__init__()
        self._kb = KeyboardInput()

    def start(self) -> None:
        self._kb.start()

    def stop(self) -> None:
        self._kb.stop()

    def get_key(self) -> str | None:
        return self._kb.get_key()

    def get_input(self, raw_keys: bool = False) -> tuple[list[str], list[int] | None]:
        """Read semantic keys from the keyboard and return them (raw_keys is ignored)."""
        keys = self._kb.read_keys(timeout=0.125)
        return (keys, None) if not raw_keys else (keys, None)
