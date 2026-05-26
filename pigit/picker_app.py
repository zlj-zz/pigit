"""
Module: pigit/picker_app.py
Description: Picker infrastructure: data models, filters, header component, and shared state.
Author: Zev
Date: 2026-05-17
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

from pigit.termui import (
    Application,
    ExitEventLoop,
    HelpPanel,
    keys,
    palette,
)
from pigit.termui._component import Component
from pigit.termui.containers import Column
from pigit.termui.reactive import Signal
from pigit.termui.tty_io import terminal_size, truncate_line
from pigit.termui.widgets import InputLine, ItemList, StatusBar

if TYPE_CHECKING:
    from pigit.termui._surface import Surface, _Subsurface

PICK_EXIT_CTRL_C = 130


class PickerMode(Enum):
    """Picker interaction modes."""

    BROWSE = "browse"
    PARAM_INPUT = "param_input"


@dataclass(frozen=True)
class PickerRow:
    """One selectable row: ``title`` + ``detail`` participate in substring filter."""

    title: str
    detail: str = ""
    ref: object = None


class PickerHeader(Component):
    """Static three-line header with separator."""

    def __init__(self, title_line: str) -> None:
        super().__init__()
        self._title = title_line

    def _render_surface(self, surface: Surface | _Subsurface) -> None:
        cols = surface.width
        surface.draw_text_rgb(
            0,
            0,
            truncate_line(self._title, cols),
            fg=palette.DEFAULT_FG,
            bg=palette.DEFAULT_BG,
            style_flags=palette.STYLE_BOLD,
        )
        surface.draw_text_rgb(
            1, 0, "─" * cols, fg=palette.DEFAULT_FG_DIM, bg=palette.DEFAULT_BG
        )

    def refresh(self) -> None:
        """No-op refresh for the static header (subclasses may override)."""


class PickerState:
    """Picker-level shared state via Signals."""

    def __init__(self) -> None:
        self.selected_idx = Signal(0)
        self.filter_text = Signal("")
        self.status_text = Signal("")


class BasePickerApp(Application):
    """Reusable picker Application base class.

    Subclasses override abstract methods to implement specific pickers
    without duplicating layout, keyboard, or lifecycle code.
    """

    BINDINGS = [
        ("Q", "quit"),
        ("?", "toggle_help"),
        ("ctrl c", "abort"),
    ]
    help_popup_class = HelpPanel

    def __init__(self, *, initial_filter: str = "", alt: bool = True) -> None:
        super().__init__(input_takeover=True, alt=alt)
        self._initial_filter = initial_filter

    # --- Abstract methods: subclasses must override ---

    def get_title(self) -> str:
        """Return the picker title (shown in PickerHeader)."""
        raise NotImplementedError

    def build_list(self) -> ItemList:
        """Build and return the list component (ItemList, CheckList, etc.)."""
        raise NotImplementedError

    def on_confirm(self) -> None:
        """Callback when Enter is pressed. Usually raises ExitEventLoop."""
        raise NotImplementedError

    def get_terminal_too_small_msg(self) -> str:
        """Error message when the terminal is too small."""
        raise NotImplementedError

    def _update_status(self) -> None:
        """Update the status bar text."""
        raise NotImplementedError

    # --- Overridable hooks ---

    def build_input(self) -> InputLine:
        """Build the input line component. Subclasses may override to customize."""
        return InputLine(
            prompt="/",
            overlay_mode=True,
            visible=False,
            on_value_changed=self._on_filter,
            on_submit=self._on_filter_done,
            on_cancel=self._on_filter_done,
        )

    def on_key_extra(self, key: str) -> None:
        """Hook for subclasses to add extra key handling. Default no-op."""

    # --- Shared implementation ---

    def build_root(self) -> Component:
        self._header = PickerHeader(self.get_title())
        self._list = self.build_list()
        self._status = StatusBar()
        self._input = self.build_input()
        self._layout = Column(
            [self._header, self._list, self._status, self._input],
            heights=[2, "flex", 1, 0],
        )
        return self._layout

    def setup_root(self, root) -> None:
        if self._initial_filter:
            self._input.set_value(self._initial_filter)
            self._input._enter_overlay_mode()
            self._on_filter(self._initial_filter)
        else:
            self._update_status()

        if self._help_popup is not None:
            panel = self._help_popup._child
            panel._entries_source = None
            panel.set_entries(self._help_entries())

    def _help_entries(self) -> list[tuple[str, str]]:
        entries = [
            ("j / k", "Scroll up / down"),
            ("Enter", "Confirm selection"),
            ("/", "Filter list"),
            ("q / Esc", "Quit"),
            ("?", "Toggle help"),
            ("Ctrl+C", "Abort"),
        ]
        entries.extend(self._extra_help_entries())
        return entries

    def _extra_help_entries(self) -> list[tuple[str, str]]:
        return []

    def after_start(self) -> None:
        _, term_rows = terminal_size()
        if term_rows < 5:  # need header (2) + at least 2 list row + footer
            self.quit(exit_code=1, result_message=self.get_terminal_too_small_msg())

    def on_key(self, key: str) -> None:
        if self._input.is_visible:
            # InputLine is active (filter mode) — route keys to it.
            # ESC hides the input; everything else edits the filter text.
            if key in (keys.KEY_ESC,):
                self._input.on_key(keys.KEY_ESC)
            else:
                self._input.on_key(key)
            return
        if key in ("j", keys.KEY_DOWN):
            self._list.next()
        elif key in ("k", keys.KEY_UP):
            self._list.previous()
        elif key == "enter":
            self.on_confirm()
        elif key == "/":
            self._input._enter_overlay_mode()
            self._layout.set_heights([2, "flex", 1, 1])
        elif key in ("q", keys.KEY_ESC):
            self.quit()
        elif key == "?":
            self._help_popup.toggle()
        else:
            self.on_key_extra(key)

    def abort(self) -> None:
        """Abort picker via Ctrl+C."""
        raise ExitEventLoop("quit", exit_code=PICK_EXIT_CTRL_C, result_message=None)

    def _on_filter(self, text: str) -> None:
        self._list.set_filter(text)
        self._update_status()

    def _on_filter_done(self, _value: str = "") -> None:
        self._input._visible = False
        self._layout.set_heights([2, "flex", 1, 0])

    def toggle_help(self) -> None:
        self._help_popup.toggle()
