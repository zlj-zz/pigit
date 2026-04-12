# -*- coding: utf-8 -*-
"""
Module: pigit/termui/geometry.py
Description: Terminal column/row sizes aligned with shutil.get_terminal_size.
Author: Zev
Date: 2026-03-26
"""

from __future__ import annotations

from dataclasses import dataclass
from shutil import get_terminal_size
from typing import NamedTuple


class TerminalSize(NamedTuple):
    """Columns (width) and lines (height) as reported by the OS."""

    columns: int
    lines: int

    @classmethod
    def from_os(cls) -> "TerminalSize":
        """Read current terminal size from the environment."""

        s = get_terminal_size()
        return cls(columns=s.columns, lines=s.lines)
