# -*- coding:utf-8 -*-
import time
from math import ceil
from typing import Any, Optional

from ..common import Term, Fx, exec_cmd, shorten, get_width, render_str
from .util import TermSize


class Widget(object):
    pass


class SwtichWidget(Widget):
    def set_size(self, width: int, height: int):
        self.width = width
        self.height = height


class RowPanel(object):
    def __init__(
        self,
        cursor: Optional[str] = None,
        help_wait: float = 1.5,
        is_sub: bool = False,  # whether is sub page.
        **kwargs,
    ) -> None:
        self._is_sub = is_sub

        if not cursor or get_width(ord(cursor)) != 1:
            self.cursor = "→"
        else:
            self.cursor = cursor

        self.help_wait = help_wait

        # Initialize.
        self.cursor_row: int = 1
        self.display_range: list = [1, TermSize.height - 1]  # Allow display row range.

        self.extra = 0  # Extra occupied row.

        for key, value in kwargs.items():
            setattr(self, "_ex_{}".format(key), value)

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

    def get_raw_data(self) -> list[Any]:
        """How to get the raw data."""
        raise NotImplementedError()

    def process_raw_data(
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

    def render(self):

        # Adjust display row range.
        while self.cursor_row < self.display_range[0]:
            self.display_range = [i - 1 for i in self.display_range]
        while self.cursor_row + self.extra > self.display_range[1]:
            self.display_range = [i + 1 for i in self.display_range]

        # Every time refresh the output, need to recalculate the
        # number of additional rows, so need to reset to zero.
        self.extra = 0

        print(Term.clear_screen)  # Clear full screen.
        # Print needed display part.
        for index, item in enumerate(self.show_data, start=1):
            line, each_extra = item
            if self.display_range[0] <= index <= self.display_range[1] - self.extra:
                self.print_line(line, index == self.cursor_row)
                self.extra += each_extra

    def do(self, input_key: str):

        raw_data: list[Any] = self.get_raw_data()
        self.raw_data = raw_data
        show_data = self.process_raw_data(raw_data, TermSize.width)

        # Process key.
        if input_key in ["j", "down"]:
            # select pre file.
            self.cursor_row += 1
            cursor_row = min(self.cursor_row, len(show_data))
        elif input_key in ["k", "up"]:
            # select next file.
            self.cursor_row -= 1
            cursor_row = max(self.cursor_row, 1)
        elif input_key in ["J"]:
            # scroll down 5 lines.
            self.cursor_row += 5
            cursor_row = min(self.cursor_row, len(show_data))
        elif input_key in ["K"]:
            # scroll up 5 line
            self.cursor_row -= 5
            cursor_row = max(self.cursor_row, 1)

        elif input_key == "windows resize":
            line_diff = 0
            self.display_range[1] += line_diff
            show_data = self.process_raw_data(raw_data, TermSize.width)
        elif input_key in ["?", "h"]:
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
            refresh = self.process_keyevent(input_key, self.cursor_row)
