# -*- coding: utf-8 -*-
"""
Module: pigit/git/cmd_picker.py
Description: Built-in TTY command picker for ``pigit cmd --pick`` (j/k, filter, execute).
Author: Project Team
Date: 2026-03-22
"""

from __future__ import annotations

import shlex
import shutil
import sys
import time
from contextlib import contextmanager
from typing import Callable, List, Optional, Tuple, TYPE_CHECKING

from .cmd_catalog import CommandEntry, iter_command_entries

if TYPE_CHECKING:
    from .cmd_proxy import GitProxy

NO_TTY_MSG = (
    "`pigit cmd --pick`<error> needs an interactive terminal.\n"
    "Use `pigit cmd -l` for the full table or "
    "`pigit cmd -s <query>` / `pigit cmd --search <query>` to filter.\n"
    "See `pigit cmd -h` for more options."
)

_TERMINAL_TOO_SMALL_MSG = (
    "Terminal is too small for `pigit cmd --pick` (need room for a fixed header, "
    "at least one list row, and a footer line). Enlarge the window or use "
    "`pigit cmd -l` / `pigit cmd -s <query>`."
)

_PICK_EXIT_CTRL_C = 130

# Raw stdin bytes this module recognizes (see also inline comments at each ``if``):
#   \x1b (27)     ESC — starts ANSI/ECMA-48 escapes (CSI ``ESC [``, SS3 ``ESC O``, etc.).
#   \x03 (3)      ETX — Ctrl+C; turned into KeyboardInterrupt.
#   \x08 (8) BS   Backspace; \x7f (127) DEL — often Backspace on Unix TTYs.
#   0x40–0x7E     Inclusive range of the final byte of a CSI/SS3 sequence (``@`` through ``~``).
#   \x00 / \xe0   Windows ``msvcrt``: extended-key prefix; \xe0\x53 is often Delete.

# Separator + title + separator (+ optional "filter:" line).
_FOOTER_LINES = 1
_MIN_LIST_ROWS = 1


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


def _read_char_raw() -> str:
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


def _lone_esc_or_consume_sequence() -> bool:
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


def _read_line_cancellable(
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
            if c == "\x1b":  # ESC — lone vs CSI/SS3 handled in _posix_handle_esc_in_line
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


def _tty_ok() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def _terminal_size() -> Tuple[int, int]:
    """Return (columns, rows). Fallback if ioctl fails."""
    try:
        sz = shutil.get_terminal_size()
        return max(20, sz.columns), max(1, sz.lines)
    except OSError:
        return 80, 24


def _header_rows(has_filter_line: bool) -> int:
    """Rows used by the fixed top banner (excluding the scrolling list)."""
    return 4 if has_filter_line else 3


def _viewport_rows(term_rows: int, has_filter_line: bool) -> int:
    """Rows available for drawing list items between header and footer."""
    return term_rows - _header_rows(has_filter_line) - _FOOTER_LINES


def _pick_terminal_usable(term_rows: int, has_filter_line: bool) -> bool:
    return _viewport_rows(term_rows, has_filter_line) >= _MIN_LIST_ROWS


def _apply_filter(entries: List[CommandEntry], needle: str) -> List[CommandEntry]:
    if not needle.strip():
        return list(entries)
    q = needle.lower()
    return [
        e
        for e in entries
        if q in e.name.lower()
        or q in e.help_text.lower()
        or q in e.command_repr.lower()
    ]


def _truncate_line(text: str, max_cols: int) -> str:
    """One physical line for the picker; strip newlines and trim to width."""
    one = " ".join(text.split())
    if max_cols <= 0:
        return ""
    if len(one) <= max_cols:
        return one
    if max_cols <= 1:
        return one[:max_cols]
    return one[: max_cols - 1] + "…"


def run_command_picker(
    proxy: "GitProxy",
    *,
    read_char: Callable[[], str] = _read_char_raw,
    write: Callable[[str], None] = sys.stdout.write,
    flush: Callable[[], None] = sys.stdout.flush,
    read_line: Callable[[str], str] = lambda p: input(p),
) -> Tuple[int, Optional[str]]:
    """
    Interactive picker over ``proxy`` commands.

    Returns:
        (exit_code, message). ``exit_code`` 0 with ``None`` means user quit with ``q``.
        ``130`` after **Ctrl+C**. Non-zero ``exit_code`` is an error; ``message`` is
        user-facing text. On successful command run, returns ``(0, output_string)``.
    """
    if not _tty_ok():
        return 1, NO_TTY_MSG

    try:
        return _run_command_picker_loop(
            proxy,
            read_char=read_char,
            write=write,
            flush=flush,
            read_line=read_line,
        )
    except KeyboardInterrupt:
        write("\n")
        flush()
        return _PICK_EXIT_CTRL_C, None


def _run_command_picker_loop(
    proxy: "GitProxy",
    *,
    read_char: Callable[[], str],
    write: Callable[[str], None],
    flush: Callable[[], None],
    read_line: Callable[[str], str],
) -> Tuple[int, Optional[str]]:
    all_entries = iter_command_entries(proxy.cmds, proxy.extra_cmd_keys)
    needle = ""
    filtered = list(all_entries)
    index = 0
    scroll_offset = 0

    def render_help_line(entry: CommandEntry) -> str:
        return proxy.generate_help_by_key(entry.name, use_color=False)

    def _sync_scroll(viewport: int) -> None:
        nonlocal scroll_offset
        if not filtered:
            scroll_offset = 0
            return
        n = len(filtered)
        if n <= viewport:
            scroll_offset = 0
            return
        if index < scroll_offset:
            scroll_offset = index
        elif index >= scroll_offset + viewport:
            scroll_offset = index - viewport + 1
        max_scroll = n - viewport
        scroll_offset = max(0, min(scroll_offset, max_scroll))

    def redraw() -> Optional[str]:
        """Redraw full-screen UI. Return error message if the terminal is too small."""
        nonlocal index
        cols, term_rows = _terminal_size()
        has_filter = bool(needle)
        if not _pick_terminal_usable(term_rows, has_filter):
            return _TERMINAL_TOO_SMALL_MSG

        viewport = _viewport_rows(term_rows, has_filter)

        if not filtered:
            # Erase display and cursor home (ANSI); full-screen redraw.
            write("\033[2J\033[H")
            sep = "=" * min(72, cols)
            write(sep + "\n")
            title = (
                "pigit cmd --pick  [j/k  Enter  /  q/Esc  Ctrl+C  "
                "1-9+Enter]"
            )
            write(_truncate_line(title, cols) + "\n")
            write(sep + "\n")
            if has_filter:
                write(_truncate_line(f"filter: {needle!r}", cols) + "\n")
            msg = (
                "No matches. Press / to edit filter, q or Esc to quit, "
                "Ctrl+C to abort."
            )
            for _ in range(viewport):
                write(_truncate_line(msg, cols) + "\n")
                msg = ""
            write(_truncate_line("--", cols) + "\n")
            flush()
            return None

        if index >= len(filtered):
            index = len(filtered) - 1
        if index < 0:
            index = 0

        _sync_scroll(viewport)

        write("\033[2J\033[H")  # clear screen + home
        sep = "=" * min(72, cols)
        write(sep + "\n")
        title = (
            "pigit cmd --pick  [j/k scroll  Enter run  / filter  q/Esc quit  "
            "Ctrl+C abort  1-9+Enter]"
        )
        write(_truncate_line(title, cols) + "\n")
        write(sep + "\n")
        if has_filter:
            write(_truncate_line(f"filter: {needle!r}", cols) + "\n")

        for row in range(viewport):
            li = scroll_offset + row
            if li >= len(filtered):
                write("\n")
                continue
            ent = filtered[li]
            prefix = "> " if li == index else "  "
            raw = render_help_line(ent).lstrip()
            body = _truncate_line(raw, cols - len(prefix))
            write(prefix + body + "\n")

        n = len(filtered)
        if n > viewport:
            lo = scroll_offset + 1
            hi = min(scroll_offset + viewport, n)
            foot = f"-- rows {lo}-{hi} of {n} (j/k scroll) --"
        else:
            foot = f"-- {n} command(s) --"
        write(_truncate_line(foot, cols) + "\n")
        flush()
        return None

    def _echo_number_at_bottom(number_buf: str) -> None:
        """Show multi-digit index input on the last screen row (below the status footer)."""
        cols, term_rows = _terminal_size()
        line = _truncate_line(f"# {number_buf} — Enter to run", cols)
        # CUP: row ``term_rows`` col 1; EL: clear to end of line.
        write(f"\033[{term_rows};1H\033[K{line}")
        flush()

    def _clear_bottom_status_row() -> None:
        _, term_rows = _terminal_size()
        write(f"\033[{term_rows};1H\033[K")  # move to last row; clear line
        flush()

    def execute(entry: CommandEntry) -> Optional[Tuple[int, Optional[str]]]:
        spec = proxy.cmds.get(entry.name) or {}
        cmd = spec.get("command")
        if cmd is None:
            return 1, "`Invalid command entry (no command).`<error>"

        if isinstance(cmd, str):
            if not entry.has_arguments:
                return 0, proxy.do(entry.name, [])
            write(
                "\nAppend arguments after the short command "
                "(empty line = run without extra args). Esc cancels.\n"
                f"pigit cmd {entry.name} "
            )
            flush()
            extra_raw = _read_line_cancellable(write=write, flush=flush, prompt="")
            if extra_raw is None:
                return None
            extra_args = shlex.split(extra_raw.strip()) if extra_raw.strip() else []
            return 0, proxy.do(entry.name, extra_args)

        write("\nThis entry runs a Python handler (not a shell git line). Esc cancels.\n")
        flush()
        extra_raw = _read_line_cancellable(write=write, flush=flush, prompt="args> ")
        if extra_raw is None:
            return None
        extra_args = shlex.split(extra_raw.strip()) if extra_raw.strip() else []
        return 0, proxy.do(entry.name, extra_args)

    # Worst-case header includes filter line so small terminals fail before UI.
    _, initial_rows = _terminal_size()
    if not _pick_terminal_usable(initial_rows, True):
        return 1, _TERMINAL_TOO_SMALL_MSG

    while True:
        layout_err = redraw()
        if layout_err:
            return 1, layout_err

        try:
            ch = read_char()
        except (OSError, AttributeError, ValueError):
            write(
                "\nSingle-key input is not available; "
                "enter a line: [number] to run, q to quit, /text to filter.\n"
            )
            flush()
            try:
                line = read_line("pick> ").strip()
            except KeyboardInterrupt:
                write("\n")
                flush()
                return _PICK_EXIT_CTRL_C, None
            if line.lower() in ("q", "quit"):
                return 0, None
            if line.startswith("/"):
                needle = line[1:]
                filtered = _apply_filter(all_entries, needle)
                index = 0
                scroll_offset = 0
                continue
            if line.isdigit():
                n = int(line)
                if 1 <= n <= len(filtered):
                    out = execute(filtered[n - 1])
                    if out is not None:
                        return out
                else:
                    write(f"Invalid index {n} (1-{len(filtered)}).\n")
                    flush()
                continue
            write("Unrecognized input; try a number, /keyword, or q.\n")
            flush()
            continue

        if ch in ("\r", "\n"):
            if not filtered:
                continue
            out = execute(filtered[index])
            if out is not None:
                return out
            continue

        if ch in ("j", "J"):
            if filtered:
                index = (index + 1) % len(filtered)
            continue

        if ch in ("k", "K"):
            if filtered:
                index = (index - 1) % len(filtered)
            continue

        if ch in ("q", "Q"):
            return 0, None

        if ch == "\x1b":  # ESC — lone: quit picker; CSI: consume (e.g. arrows)
            if _lone_esc_or_consume_sequence():
                return 0, None
            continue

        if ch == "/":
            write("filter keyword (empty clears, Esc cancels): ")
            flush()
            new_needle = _read_line_cancellable(write=write, flush=flush, prompt="")
            if new_needle is None:
                continue
            needle = new_needle
            filtered = _apply_filter(all_entries, needle)
            index = 0
            scroll_offset = 0
            continue

        if ch.isdigit():
            buf = ch
            _echo_number_at_bottom(buf)
            while True:
                try:
                    c = read_char()
                except KeyboardInterrupt:
                    _clear_bottom_status_row()
                    write("\n")
                    flush()
                    return _PICK_EXIT_CTRL_C, None
                if c in ("\r", "\n"):
                    break
                # ESC — cancel numeric entry if lone; else swallow CSI (arrow keys).
                if c == "\x1b":
                    if _lone_esc_or_consume_sequence():
                        _clear_bottom_status_row()
                        break
                    continue
                if c.isdigit():
                    buf += c
                    _echo_number_at_bottom(buf)
                else:
                    _clear_bottom_status_row()
                    break
            try:
                num = int(buf)
            except ValueError:
                _clear_bottom_status_row()
                continue
            if filtered and 1 <= num <= len(filtered):
                _clear_bottom_status_row()
                out = execute(filtered[num - 1])
                if out is not None:
                    return out
            else:
                _clear_bottom_status_row()
            continue
