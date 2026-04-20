# -*- coding: utf-8 -*-
"""
Module: pigit/termui/picker_layout.py
Description: Picker viewport math and terminal size validation.
Author: Zev
Date: 2026-03-27
"""

from __future__ import annotations

from .tty_io import MIN_LIST_ROWS

PICKER_HEADER_ROWS = 3
PICKER_FOOTER_ROWS = 2


def picker_viewport(term_rows: int) -> int:
    """List rows between the fixed header and two pinned bottom rows."""

    return term_rows - PICKER_HEADER_ROWS - PICKER_FOOTER_ROWS


def picker_terminal_ok(term_rows: int) -> bool:
    """Whether the terminal has enough rows for header, list, and footer."""

    return picker_viewport(term_rows) >= MIN_LIST_ROWS
