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
from typing import TYPE_CHECKING, Optional, Sequence

from ._component_base import Component
from ._reactive import Signal
from .event_loop import ExitEventLoop
from .tty_io import truncate_line

if TYPE_CHECKING:
    from ._surface import Surface

PICK_EXIT_CTRL_C = 130


class PickerMode(Enum):
    """Picker interaction modes."""

    BROWSE = "browse"
    FILTER = "filter"


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

    NAME = "picker_header"

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


class PickerAppMixin:
    """Shared picker logic for Application subclasses.

    Assumes the subclass has set the following attributes in ``__init__``
    or ``build_root``:

    - ``_mode`` (:class:`PickerMode`)
    - ``_input`` (:class:`~pigit.termui._component_widgets.InputLine`)
    - ``_layout`` (:class:`~pigit.termui._component_layouts.Column`)
    - ``_list`` (:class:`~pigit.termui._component_widgets.ItemSelector`)
    - ``_rows`` (sequence of :class:`PickerRow`)
    - ``_filtered_rows`` (list of :class:`PickerRow`)
    - ``_state`` (:class:`PickerState`)
    - ``_loop`` (event loop with ``get_term_size`` and ``render``)
    - ``_help_popup`` (overlay toggleable)
    """

    def _on_filter(self, key: str) -> None:
        if key == "enter":
            self._exit_filter()
        elif key == "esc":
            self._input.clear()
            self._exit_filter()
        elif key == "backspace":
            self._input.backspace()
            self._apply_filter()
        elif key == "ctrl c":
            self.quit(exit_code=PICK_EXIT_CTRL_C)
        elif len(key) == 1 and key.isprintable() and ord(key) >= 32:
            self._input.insert(key)
            self._apply_filter()

    def _enter_filter(self) -> None:
        self._mode = PickerMode.FILTER
        self._input.set_visible(True)
        self._layout.set_heights([3, "flex", 1, 1])
        self.resize(self._loop.get_term_size())

    def _exit_filter(self) -> None:
        self._mode = PickerMode.BROWSE
        self._input.set_visible(False)
        self._layout.set_heights([3, "flex", 1, 0])
        self.resize(self._loop.get_term_size())

    def _apply_filter(self) -> None:
        needle = self._input.value
        filtered = apply_picker_filter(self._rows, needle)
        self._filtered_rows = filtered
        self._list.set_content([self._format_row(r) for r in filtered])
        self._list.curr_no = 0
        self._state.selected_idx.set(0)
        self._update_status(0)

    def _update_status(self, idx: int) -> None:
        n = len(self._list.content)
        vp = self._list.visible_row_count
        if n > vp:
            lo = self._list.viewport_start + 1
            hi = min(self._list.viewport_start + vp, n)
            text = f"-- rows {lo}-{hi} of {n} --"
        else:
            text = f"-- {n} row(s) --"
        self._state.status_text.set(text)

    def _format_row(self, row: PickerRow) -> str:
        """Subclasses override to control row rendering."""
        return f"{row.title}  {row.detail}"

    def quit(self, exit_code: int = 0, result_message: Optional[str] = None) -> None:
        raise ExitEventLoop("quit", exit_code=exit_code, result_message=result_message)

    def toggle_help(self) -> None:
        self._help_popup.toggle()


