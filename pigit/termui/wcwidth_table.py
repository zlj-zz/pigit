"""
Module: pigit/termui/wcwidth_table.py
Description: Display-width helpers for terminal column counting.
Author: Zev
Date: 2026-03-27
"""

from __future__ import annotations

import unicodedata
from bisect import bisect_right
from functools import lru_cache

#: Emoji presentation selector.
_VS16 = "\ufe0f"

#: Code points a following U+FE0F widens from one column to two. These are the
#: `emoji variation sequences`_ UTS #51 marks narrow but emoji-presenting;
#: ``unicodedata`` exposes no variation-selector data, so the ranges live here.
#: Sorted and disjoint, so :func:`_vs16_widens` can binary-search them.
#:
#: .. _emoji variation sequences: https://www.unicode.org/Public/UCD/latest/ucd/emoji/emoji-variation-sequences.txt
_VS16_WIDE = (
    (0x0023, 0x0023), (0x002A, 0x002A), (0x0030, 0x0039), (0x00A9, 0x00A9), (0x00AE, 0x00AE),
    (0x203C, 0x203C), (0x2049, 0x2049), (0x2122, 0x2122), (0x2139, 0x2139), (0x2194, 0x2199),
    (0x21A9, 0x21AA), (0x2328, 0x2328), (0x23CF, 0x23CF), (0x23ED, 0x23EF), (0x23F1, 0x23F2),
    (0x23F8, 0x23FA), (0x24C2, 0x24C2), (0x25AA, 0x25AB), (0x25B6, 0x25B6), (0x25C0, 0x25C0),
    (0x25FB, 0x25FC), (0x2600, 0x2604), (0x260E, 0x260E), (0x2611, 0x2611), (0x2618, 0x2618),
    (0x261D, 0x261D), (0x2620, 0x2620), (0x2622, 0x2623), (0x2626, 0x2626), (0x262A, 0x262A),
    (0x262E, 0x262F), (0x2638, 0x263A), (0x2640, 0x2640), (0x2642, 0x2642), (0x265F, 0x2660),
    (0x2663, 0x2663), (0x2665, 0x2666), (0x2668, 0x2668), (0x267B, 0x267B), (0x267E, 0x267E),
    (0x2692, 0x2692), (0x2694, 0x2697), (0x2699, 0x2699), (0x269B, 0x269C), (0x26A0, 0x26A0),
    (0x26A7, 0x26A7), (0x26B0, 0x26B1), (0x26C8, 0x26C8), (0x26CF, 0x26CF), (0x26D1, 0x26D1),
    (0x26D3, 0x26D3), (0x26E9, 0x26E9), (0x26F0, 0x26F1), (0x26F4, 0x26F4), (0x26F7, 0x26F9),
    (0x2702, 0x2702), (0x2708, 0x2709), (0x270C, 0x270D), (0x270F, 0x270F), (0x2712, 0x2712),
    (0x2714, 0x2714), (0x2716, 0x2716), (0x271D, 0x271D), (0x2721, 0x2721), (0x2733, 0x2734),
    (0x2744, 0x2744), (0x2747, 0x2747), (0x2763, 0x2764), (0x27A1, 0x27A1), (0x2934, 0x2935),
    (0x2B05, 0x2B07), (0x1F170, 0x1F171), (0x1F17E, 0x1F17F), (0x1F321, 0x1F321),
    (0x1F324, 0x1F32C), (0x1F336, 0x1F336), (0x1F37D, 0x1F37D), (0x1F396, 0x1F397),
    (0x1F399, 0x1F39B), (0x1F39E, 0x1F39F), (0x1F3CB, 0x1F3CE), (0x1F3D4, 0x1F3DF),
    (0x1F3F3, 0x1F3F3), (0x1F3F5, 0x1F3F5), (0x1F3F7, 0x1F3F7), (0x1F43F, 0x1F43F),
    (0x1F441, 0x1F441), (0x1F4FD, 0x1F4FD), (0x1F549, 0x1F54A), (0x1F56F, 0x1F570),
    (0x1F573, 0x1F579), (0x1F587, 0x1F587), (0x1F58A, 0x1F58D), (0x1F590, 0x1F590),
    (0x1F5A5, 0x1F5A5), (0x1F5A8, 0x1F5A8), (0x1F5B1, 0x1F5B2), (0x1F5BC, 0x1F5BC),
    (0x1F5C2, 0x1F5C4), (0x1F5D1, 0x1F5D3), (0x1F5DC, 0x1F5DE), (0x1F5E1, 0x1F5E1),
    (0x1F5E3, 0x1F5E3), (0x1F5E8, 0x1F5E8), (0x1F5EF, 0x1F5EF), (0x1F5F3, 0x1F5F3),
    (0x1F5FA, 0x1F5FA), (0x1F6CB, 0x1F6CB), (0x1F6CD, 0x1F6CF), (0x1F6E0, 0x1F6E5),
    (0x1F6E9, 0x1F6E9), (0x1F6F0, 0x1F6F0), (0x1F6F3, 0x1F6F3),
)

_VS16_STARTS = tuple(start for start, _ in _VS16_WIDE)


@lru_cache(maxsize=256)
def _vs16_widens(r: int) -> bool:
    """Return whether U+FE0F after *r* makes it two columns wide."""
    index = bisect_right(_VS16_STARTS, r) - 1
    return index >= 0 and r <= _VS16_WIDE[index][1]


@lru_cache(maxsize=1024)
def get_width(r: int) -> int:
    """Return the display width (columns) for a single Unicode code point.

    Nonspacing and enclosing marks are zero-width. ``category`` is checked
    alongside ``combining`` because 1,126 ``Mn``/``Me`` code points report a
    combining class of 0 -- CGJ, VS16 and the keycap mark among them -- and
    ``combining`` alone would give them a column. The VS16 widening that this
    leaves out is applied by :func:`char_width_at`, which can see the sequence.
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


def char_width_at(text: str, index: int) -> int:
    """Return the columns the character at *index* occupies.

    A one-column base followed by VS16 is drawn as a two-column emoji when UTS
    #51 lists that variation sequence, so the selector folds into its base
    rather than counting on its own -- a terminal advances two columns for
    ``U+2764 U+FE0F``. Keycaps follow the same rule: the digit widens, and the
    selector and enclosing mark that trail it stay zero-width.
    """
    ch = text[index]
    w = 1 if ch.isascii() else _char_width(ord(ch))
    if (
        w == 1
        and index + 1 < len(text)
        and text[index + 1] == _VS16
        and _vs16_widens(ord(ch))
    ):
        return 2
    return w


def wcswidth(text: str) -> int:
    """Return display width of *text* in terminal columns.

    Widths follow ``unicodedata`` -- East Asian Wide/Fullwidth count as two
    columns, combining marks as zero, everything else as one -- with one
    sequence rule on top: a U+FE0F selector widens the base it follows, which
    :func:`char_width_at` applies per position. Sequences that still disagree
    with a terminal: VS15 text presentation (a wide base plus U+FE0E), ZWJ
    families and skin-tone modifiers come out wider, and U+200B/200D count as
    one.
    """
    return sum(char_width_at(text, index) for index in range(len(text)))


def truncate_by_width(text: str, max_width: int) -> str:
    """Truncate text so that its display width <= max_width."""
    if max_width <= 0:
        return ""
    width = 0
    parts = []
    for index, cp in enumerate(text):
        w = char_width_at(text, index)
        if width + w > max_width:
            break
        parts.append(cp)
        width += w
    return "".join(parts)


def _drop_orphan_marks(text: str, index: int) -> str:
    """Return ``text[index:]`` without the combining marks that lead it.

    The cut at *index* just dropped the base character those marks attach to.
    Keeping them re-attaches them to whatever is now to their left — the blank
    left behind by a half-cut wide glyph, or the previous word. A VS16 orphan
    goes with them: without its base it widens nothing.
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
    for index in range(len(text)):
        w = char_width_at(text, index)
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
