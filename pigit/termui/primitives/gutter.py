"""
Module: pigit/termui/primitives/gutter.py
Description: Minimal line-number gutter formatting for diff viewers.
Author: Zev
Date: 2026-08-20
"""

from __future__ import annotations


def format_line_number(value: int | str, width: int) -> str:
    """Right-justify ``value`` (or blank string) to ``width`` display columns.

    Args:
        value: Line number or empty string for non-numbered rows.
        width: Target display width in terminal columns.

    Returns:
        Right-padded string of length ``width``.
    """
    if value == "":
        return "".rjust(width)
    text = str(value)
    # Keep the rightmost digits when the number outgrows the gutter
    # (e.g. 10000 in a 4-wide column); rjust alone would overflow and
    # collide with the +/- prefix column.
    if len(text) > width:
        text = text[-width:]
    return text.rjust(width)
