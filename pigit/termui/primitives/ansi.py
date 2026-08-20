# -*- coding: utf-8 -*-
"""
Module: pigit/termui/primitives/ansi.py
Description: Parse ANSI SGR sequences into styled Segments for Surface drawing.
Author: Zev
Date: 2026-08-20
"""

from __future__ import annotations

import re

from .. import palette
from .._color import _ANSI_16_PALETTE, xterm256_to_rgb
from ..segment import Segment

_OSC_RE = re.compile(r"\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)")
_CSI_FINAL_MIN = 0x40
_CSI_FINAL_MAX = 0x7E

SgrState = tuple[
    tuple[int, int, int] | None,
    tuple[int, int, int] | None,
    int,
]


def parse_ansi_line(text: str) -> list[Segment]:
    """Parse one line of SGR-colored text into styled segments.

    OSC hyperlinks are stripped. Non-SGR CSI sequences are skipped.
    """
    text = _OSC_RE.sub("", text)
    segs: list[Segment] = []
    buf: list[str] = []
    state: SgrState = (None, None, 0)

    def flush() -> None:
        if not buf:
            return
        fg, bg, flags = state
        segs.append(Segment("".join(buf), fg=fg, bg=bg, style_flags=flags))
        buf.clear()

    i = 0
    n = len(text)
    while i < n:
        if text[i] != "\x1b":
            buf.append(text[i])
            i += 1
            continue
        flush()
        i, state = _consume_escape(text, i, state)
    flush()
    return segs


def _consume_escape(text: str, index: int, state: SgrState) -> tuple[int, SgrState]:
    """Advance past an ESC sequence; apply SGR when the final byte is ``m``."""
    n = len(text)
    if index + 1 >= n:
        return n, state
    if text[index + 1] != "[":
        return index + 2, state
    cursor = index + 2
    while cursor < n and not (_CSI_FINAL_MIN <= ord(text[cursor]) <= _CSI_FINAL_MAX):
        cursor += 1
    if cursor >= n:
        return n, state
    final = text[cursor]
    if final == "m":
        state = _apply_sgr(state, _sgr_params(text[index + 2 : cursor]))
    return cursor + 1, state


def _sgr_params(body: str) -> list[int]:
    """Split a CSI parameter string into integers (empty means reset)."""
    if not body:
        return [0]
    values: list[int] = []
    for part in body.split(";"):
        if part == "":
            values.append(0)
            continue
        try:
            values.append(int(part))
        except ValueError:
            continue
    return values or [0]


def _apply_sgr(state: SgrState, params: list[int]) -> SgrState:
    """Return a new SGR state after applying ``params`` in order."""
    fg, bg, flags = state
    index = 0
    while index < len(params):
        code = params[index]
        if code in (38, 48):
            color, index = _extended_color(params, index)
            if color is not None:
                if code == 38:
                    fg = color
                else:
                    bg = color
            continue
        fg, bg, flags = _apply_sgr_code(fg, bg, flags, code)
        index += 1
    return (fg, bg, flags)


def _extended_color(
    params: list[int], index: int
) -> tuple[tuple[int, int, int] | None, int]:
    """Parse ``38/48;5;n`` or ``38/48;2;r;g;b`` starting at ``index``."""
    if index + 1 >= len(params):
        return None, index + 1
    mode = params[index + 1]
    if mode == 5 and index + 2 < len(params):
        return xterm256_to_rgb(params[index + 2]), index + 3
    if mode == 2 and index + 4 < len(params):
        red, green, blue = params[index + 2], params[index + 3], params[index + 4]
        return (_clamp8(red), _clamp8(green), _clamp8(blue)), index + 5
    return None, index + 2


def _clamp8(value: int) -> int:
    return max(0, min(255, value))


def _apply_sgr_code(
    fg: tuple[int, int, int] | None,
    bg: tuple[int, int, int] | None,
    flags: int,
    code: int,
) -> SgrState:
    """Apply a single non-extended SGR code."""
    if code == 0:
        return None, None, 0
    if code == 1:
        return fg, bg, flags | palette.STYLE_BOLD
    if code == 2:
        return fg, bg, flags | palette.STYLE_DIM
    if code == 3:
        return fg, bg, flags | palette.STYLE_ITALIC
    if code == 4:
        return fg, bg, flags | palette.STYLE_UNDERLINE
    if code == 7:
        return fg, bg, flags | palette.STYLE_REVERSE
    if code == 22:
        return fg, bg, flags & ~(palette.STYLE_BOLD | palette.STYLE_DIM)
    if code == 23:
        return fg, bg, flags & ~palette.STYLE_ITALIC
    if code == 24:
        return fg, bg, flags & ~palette.STYLE_UNDERLINE
    if code == 27:
        return fg, bg, flags & ~palette.STYLE_REVERSE
    if 30 <= code <= 37:
        return _ANSI_16_PALETTE[code - 30], bg, flags
    if 90 <= code <= 97:
        return _ANSI_16_PALETTE[code - 90 + 8], bg, flags
    if code == 39:
        return None, bg, flags
    if 40 <= code <= 47:
        return fg, _ANSI_16_PALETTE[code - 40], flags
    if 100 <= code <= 107:
        return fg, _ANSI_16_PALETTE[code - 100 + 8], flags
    if code == 49:
        return fg, None, flags
    return fg, bg, flags
