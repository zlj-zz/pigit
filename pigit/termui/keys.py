# -*- coding: utf-8 -*-
"""
Module: pigit/termui/keys.py
Description: Semantic key strings and golden escape-sequence tables for KeyboardInput.
Author: Project Team
Date: 2026-03-26
"""

from __future__ import annotations

from typing import Dict, Iterator, List, Tuple

# Stable semantic tokens (public documentation; values match existing app conventions).
KEY_TAB = "tab"
KEY_ENTER = "enter"
KEY_BACKSPACE = "backspace"
KEY_ESC = "esc"
KEY_UP = "up"
KEY_DOWN = "down"
KEY_LEFT = "left"
KEY_RIGHT = "right"
KEY_HOME = "home"
KEY_END = "end"
KEY_PAGE_UP = "page up"
KEY_PAGE_DOWN = "page down"
KEY_DELETE = "delete"
KEY_INSERT = "insert"
KEY_WINDOW_RESIZE = "window resize"

# CSI / SS3 sequences (bytes -> semantic). Longest-match wins at parse time.
ESC_TO_SEMANTIC: Dict[bytes, str] = {
    # Arrow keys (CSI)
    b"\x1b[A": KEY_UP,
    b"\x1b[B": KEY_DOWN,
    b"\x1b[C": KEY_RIGHT,
    b"\x1b[D": KEY_LEFT,
    # SS3 (some terminals)
    b"\x1bOA": KEY_UP,
    b"\x1bOB": KEY_DOWN,
    b"\x1bOC": KEY_RIGHT,
    b"\x1bOD": KEY_LEFT,
    # Home / End
    b"\x1b[H": KEY_HOME,
    b"\x1b[F": KEY_END,
    b"\x1b[1~": KEY_HOME,
    b"\x1b[4~": KEY_END,
    # Page / edit
    b"\x1b[5~": KEY_PAGE_UP,
    b"\x1b[6~": KEY_PAGE_DOWN,
    b"\x1b[3~": KEY_DELETE,
    b"\x1b[2~": KEY_INSERT,
    b"\x1b[Z": "shift tab",
    # Function keys (common xterm-style)
    b"\x1bOP": "f1",
    b"\x1bOQ": "f2",
    b"\x1bOR": "f3",
    b"\x1bOS": "f4",
    b"\x1b[11~": "f1",
    b"\x1b[12~": "f2",
    b"\x1b[13~": "f3",
    b"\x1b[14~": "f4",
}


def iter_esc_sequences_longest_first() -> Iterator[Tuple[bytes, str]]:
    """Yield (sequence, semantic) with longest byte sequences first for prefix-safe matching."""

    items: List[Tuple[bytes, str]] = list(ESC_TO_SEMANTIC.items())
    items.sort(key=lambda x: len(x[0]), reverse=True)
    yield from items


def ctrl_letter_semantic(byte: int) -> str:
    """Map 1..26 to ctrl a..z (for use after filtering tab/lf/cr)."""

    return "ctrl " + chr(ord("a") + byte - 1)


# Windows msvcrt: extended scancode after prefix b'\\x00' or b'\\xe0'
# Second byte maps to semantic string (aligned with POSIX names).
WIN_EXT_TO_SEMANTIC: Dict[bytes, str] = {
    b"\xe0H": KEY_UP,
    b"\xe0P": KEY_DOWN,
    b"\xe0K": KEY_LEFT,
    b"\xe0M": KEY_RIGHT,
    b"\xe0G": KEY_HOME,
    b"\xe0O": KEY_END,
    b"\xe0I": KEY_PAGE_UP,
    b"\xe0Q": KEY_PAGE_DOWN,
    b"\xe0S": KEY_DELETE,
    # Duplicate with \xe0 prefix for some keyboards
    b"\x00H": KEY_UP,
    b"\x00P": KEY_DOWN,
    b"\x00K": KEY_LEFT,
    b"\x00M": KEY_RIGHT,
}


def is_mouse_event(ev: object) -> bool:
    """
    Return True if ``ev`` is a legacy 4-tuple mouse event from a custom
    :class:`~pigit.termui.input_terminal.InputTerminal`.

    ``KeyboardInput`` / :class:`~pigit.termui.tui_input_bridge.TermuiInputBridge`
    emit semantic strings only; tuple events are optional for injected terminals
    that still mirror the old Urwid-style mouse shape.
    """

    if not isinstance(ev, tuple) or len(ev) != 4:
        return False
    head = ev[0]
    return isinstance(head, str) and "mouse" in head
