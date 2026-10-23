"""
Module: pigit/termui/wcwidth_table.py
Description: Display-width helpers for terminal column counting.
Author: Zev
Date: 2026-03-27
"""

from __future__ import annotations

import unicodedata
from functools import lru_cache


@lru_cache(maxsize=1024)
def get_width(r: int) -> int:
    """Return the display width (columns) for a single Unicode code point.

    Nonspacing and enclosing marks are zero-width. ``category`` is checked
    alongside ``combining`` because 1,126 ``Mn``/``Me`` code points report a
    combining class of 0 -- CGJ, VS16 and the keycap mark among them -- and
    ``combining`` alone would give them a column.
    """
    if not 0 <= r <= 0x10FFFF:
        return 1
    ch = chr(r)
    if unicodedata.combining(ch) or unicodedata.category(ch) in ("Mn", "Me"):
        return 0
    return 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1


def _char_width(o: int) -> int:
    """Return display width for a single code point, with control-char fallback."""
    if o < 32 or o == 0x7F:
        return 1
    return get_width(o)


def wcswidth(text: str) -> int:
    """Return display width of *text* in terminal columns.

    Widths follow ``unicodedata``: East Asian Wide/Fullwidth count as two
    columns, combining marks as zero, everything else as one. The sum is per
    code point, so a sequence a terminal composes into one glyph can disagree:
    VS16 emoji and keycaps come out a column short, while ZWJ families and
    skin-tone modifiers come out wider. Grapheme clustering is not modelled.
    U+200B/200D and other zero-width format characters still count as one.
    """
    return sum(_char_width(ord(cp)) for cp in text)


def truncate_by_width(text: str, max_width: int) -> str:
    """Truncate text so that its display width <= max_width."""
    if max_width <= 0:
        return ""
    width = 0
    parts = []
    for cp in text:
        w = _char_width(ord(cp))
        if width + w > max_width:
            break
        parts.append(cp)
        width += w
    return "".join(parts)


def _drop_orphan_marks(text: str, index: int) -> str:
    """Return ``text[index:]`` without the combining marks that lead it.

    The cut at *index* just dropped the base character those marks attach to.
    Keeping them re-attaches them to whatever is now to their left — the blank
    left behind by a half-cut wide glyph, or the previous word.
    """
    while index < len(text) and _char_width(ord(text[index])) == 0:
        index += 1
    return text[index:]


def slice_left_by_width(text: str, skip: int) -> str:
    """Drop *skip* display columns from the left of *text*.

    The result preserves ``wcswidth(result) == max(0, wcswidth(text) - skip)``.
    That invariant is the whole point: callers lay out whatever follows this
    string by column, so returning anything narrower would shift the rest of
    the line left by the difference. A cut that lands inside a wide glyph
    therefore occupies the glyph's remaining columns with blanks — a terminal
    cannot draw half a glyph either.
    """
    if skip <= 0:
        return text
    width = 0
    for index, cp in enumerate(text):
        w = _char_width(ord(cp))
        if width + w > skip:
            return " " * (w - (skip - width)) + _drop_orphan_marks(text, index + 1)
        width += w
        if width == skip:
            return _drop_orphan_marks(text, index + 1)
    return ""


def pad_by_width(text: str, width: int) -> str:
    """Pad text with spaces on the right to reach the given display width."""
    pad = width - wcswidth(text)
    if pad > 0:
        return text + " " * pad
    return text
