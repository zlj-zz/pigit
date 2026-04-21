# -*- coding: utf-8 -*-
"""
Module: pigit/termui/_picker.py
Description: Full-screen searchable list picker as a Component driven by AppEventLoop.
Author: Zev
Date: 2026-04-19
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Sequence

from ._component_base import Component
from ._reactive import Signal
from .tty_io import truncate_line, MIN_LIST_ROWS

if TYPE_CHECKING:
    from ._surface import Surface

PICK_EXIT_CTRL_C = 130

PICKER_HEADER_ROWS = 3
PICKER_FOOTER_ROWS = 2


def picker_viewport(term_rows: int) -> int:
    """List rows between the fixed header and two pinned bottom rows."""

    return term_rows - PICKER_HEADER_ROWS - PICKER_FOOTER_ROWS


def picker_terminal_ok(term_rows: int) -> bool:
    """Whether the terminal has enough rows for header, list, and footer."""

    return picker_viewport(term_rows) >= MIN_LIST_ROWS


class PickerMode(Enum):
    """Picker interaction modes."""

    BROWSE = "browse"
    FILTER = "filter"
    PARAM_INPUT = "param_input"


@dataclass(frozen=True)
class PickerRow:
    """One selectable row: ``title`` + ``detail`` participate in substring filter."""

    title: str
    detail: str = ""
    ref: object = None


def apply_picker_filter(rows: Sequence[PickerRow], needle: str) -> list[PickerRow]:
    """Case-insensitive substring match on ``title`` and ``detail``."""

    if not needle.strip():
        return list(rows)
    q = needle.lower()
    return [r for r in rows if q in r.title.lower() or q in (r.detail or "").lower()]


class PickerHeader(Component):
    """Static three-line header with separator."""

    def __init__(self, title_line: str) -> None:
        super().__init__()
        self._title = title_line

    def _render_surface(self, surface: "Surface") -> None:
        cols = surface.width
        sep = "=" * min(72, cols)
        surface.draw_text(0, 0, sep)
        surface.draw_text(1, 0, truncate_line(self._title, cols))
        surface.draw_text(2, 0, sep)

    def fresh(self) -> None:
        pass


class PickerState:
    """Picker-level shared state via Signals."""

    def __init__(self) -> None:
        self.selected_idx = Signal(0)
        self.filter_text = Signal("")
        self.status_text = Signal("")
