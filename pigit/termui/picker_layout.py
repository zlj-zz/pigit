# -*- coding: utf-8 -*-
"""
Module: pigit/termui/picker_layout.py
Description: Picker viewport math, pinned-row footer text, and visual truncation helpers.
Author: Zev
Date: 2026-03-27
"""

from __future__ import annotations

from pigit.termui.tty_io import MIN_LIST_ROWS, truncate_line

PICKER_HEADER_ROWS = 3
PICKER_FOOTER_ROWS = 2


def picker_viewport(term_rows: int) -> int:
    """List rows between the fixed header and two pinned bottom rows."""

    return term_rows - PICKER_HEADER_ROWS - PICKER_FOOTER_ROWS


def picker_terminal_ok(term_rows: int) -> bool:
    """Whether the terminal has enough rows for header, list, and footer."""

    return picker_viewport(term_rows) >= MIN_LIST_ROWS


def truncate_visual(text: str, max_cols: int) -> str:
    """Trim to width without collapsing internal spaces (unlike ``truncate_line``)."""

    if max_cols <= 0:
        return ""
    if len(text) <= max_cols:
        return text
    if max_cols == 1:
        return text[0]
    return text[: max_cols - 1] + "…"


def normalize_filter_text(needle: str) -> str:
    """Single-line filter text for display and matching."""

    return needle.replace("\r", "").replace("\n", " ")


def footer_status_line(
    foot: str,
    needle: str,
    has_filter: bool,
    filter_editing: bool,
    cols: int,
) -> str:
    """
    Text for the row above the input line: ``-- … --`` or ``-- … --[filter]`` when editing.

    When not editing but a filter applies, appends ``filter: …``.
    """

    if not has_filter:
        return truncate_line(foot, cols)
    rest = normalize_filter_text(needle)
    if filter_editing:
        return truncate_visual(foot + "[filter]", cols)
    return truncate_visual(foot + "  " + "filter: " + rest, cols)


def filter_input_line(needle: str, cols: int) -> str:
    """Input/cursor line (bottom row); same row as ``#`` digit overlay."""

    rest = normalize_filter_text(needle)
    if not rest:
        return "/"
    return truncate_visual("/" + rest, cols)
