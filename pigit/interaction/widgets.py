# -*- coding:utf-8 -*-
import time
from math import ceil
from typing import Any, Optional

from ..common import Term, Fx, exec_cmd, shorten, get_width, render_str


class Widget(object):
    def _process_event(self):
        raise NotImplementedError()

    def _render(self, size):
        raise NotImplementedError()


class SwitchWidget(Widget):
    def __init__(self, sub_widgets: list = None, start_idx: int = 0):
        self.idx = start_idx

        if not sub_widgets:
            self.sub_widgets = []
            self.sub_widgets_count = 0
        else:
            self.sub_widgets = sub_widgets
            self.sub_widgets_count = len(sub_widgets)

    def add(self, widget):
        """Add new sub widget."""
        self.sub_widgets.append(widget)
        self.sub_widgets_count += 1

    def set_current(self, idx: int):
        """Set the top sub widget, if index is valid."""
        if 0 <= idx < self.sub_widgets_count:
            self.idx = idx

    def process_keyevent(self, key: str) -> Optional[int]:
        raise NotImplementedError()

    def _process_event(self, key: str):
        next_idx = self.process_keyevent(key)
        if isinstance(next_idx, int):
            self.set_current(next_idx)
        else:
            current_sub_widget = self.sub_widgets[self.idx]
            current_sub_widget._process_event(key)

    def _render(self, size):
        """
        This widget cannot render any, call current sub widget ``_render``
        """
        current_sub_widget = self.sub_widgets[self.idx]
        current_sub_widget._render(size)


class RowPanelWidget(Widget):
    def __init__(
        self,
        cursor: Optional[str] = None,
        help_wait: float = 1.5,
        is_sub: bool = False,  # whether is sub page.
        **kwargs,
    ) -> None:
        self.size = None

        self._is_sub = is_sub

        if not cursor or get_width(ord(cursor)) != 1:
            self.cursor = "→"
        else:
            self.cursor = cursor

        self.help_wait = help_wait

        # Initialize.
        self.cursor_row: int = 1
        self.display_range: list = None  # Allow display row range.

        self.extra = 0  # Extra occupied row.

        self.raw_data: list = None
        self.show_data: list = None

        self.update_raw: bool = False

        for key, value in kwargs.items():
            setattr(self, "_ex_{}".format(key), value)

    def get_raw_data(self) -> list[Any]:
        """How to get the raw data."""
        raise NotImplementedError()

    def process_raw_data(self, raw_data: list[Any]) -> list[str]:
        return raw_data

    def generate_show_data(
        self, raw_data: list[str], width: int
    ) -> list[tuple[str, int]]:
        """
        Process the raw data, and indicate the number of additional
        rows that need to be occupied when each piece of data is displayed.
        """

        new_list = []
        for line in raw_data:
            text = Fx.uncolor(line)
            count = 0
            for ch in text:
                count += get_width(ord(ch))
            # [float] is to solve the division of python2 without
            # retaining decimal places.
            new_list.append((line, ceil(count / width) - 1))
        return new_list

    def print_line(self, line: str, is_cursor_row: bool) -> None:
        """How to output one line.

        May has some different when current line is cursor line.
        Support to process cursor line specially.
        """
        raise NotImplementedError()

    def update(self):
        self.display_range = [1, self.size[1] - 1]
        self.raw_data: list[Any] = self.get_raw_data()
        self.show_data = self.generate_show_data(
            self.process_raw_data(self.raw_data), self.size[0]
        )

    def emit(self, name, cb=None):
        if name == "update":
            self.update()

    def _render(self, size):
        if self.size != size:
            self.size = size
            self.update()

        # Adjust display row range.
        while self.cursor_row < self.display_range[0]:
            self.display_range = [i - 1 for i in self.display_range]
        while self.cursor_row + self.extra > self.display_range[1]:
            self.display_range = [i + 1 for i in self.display_range]

        # Every time refresh the output, need to recalculate the
        # number of additional rows, so need to reset to zero.
        self.extra = 0

        # Print needed display part.
        for index, item in enumerate(self.show_data, start=1):
            line, each_extra = item
            if self.display_range[0] <= index <= self.display_range[1] - self.extra:
                self.print_line(line, index == self.cursor_row)
                self.extra += each_extra

    def _process_event(self, key: str):
        # Process key.
        if key in ["j", "down"]:
            # select pre file.
            self.cursor_row += 1
            self.cursor_row = min(self.cursor_row, len(self.show_data))

        elif key in ["k", "up"]:
            # select next file.
            self.cursor_row -= 1
            self.cursor_row = max(self.cursor_row, 1)

        elif key in ["J"]:
            # scroll down 5 lines.
            self.cursor_row += 5
            self.cursor_row = min(self.cursor_row, len(self.show_data))

        elif key in ["K"]:
            # scroll up 5 line
            self.cursor_row -= 5
            self.cursor_row = max(self.cursor_row, 1)

        elif key in ["?", "h"]:
            print(Term.clear_screen)
            print(
                (
                    "k / ↑: select previous line.\n"
                    "j / ↓: select next line.\n"
                    "J: Scroll down 5 lines.\n"
                    "K: Scroll down 5 lines.\n"
                    "? / h : show help, wait {}s and exit.\n" + self.keyevent_help()
                ).format(self.help_wait)
            )
            time.sleep(self.help_wait)

        else:
            self.process_keyevent(key, self.cursor_row)

    def process_keyevent(self, input_key: str, cursor_row: int) -> bool:
        """Handles keyboard events other than movement.

        Args:
            input_key (str): keyboard string.
            cursor_row (int): current line.
            data (Any): raw data.

        Returns:
            bool: whether need refresh data.
        """
        raise NotImplementedError()

    def keyevent_help(self) -> str:
        """Get extra keyevent help message.

        Returns:
            str: help message string.
        """
        raise NotImplementedError()
