# -*- coding:utf-8 -*-
from typing import Any, Callable, List, Optional, Tuple
from abc import ABC, abstractmethod
import time
from math import ceil

from plenty.str_utils import get_width
from plenty.style import Style

from .console import Term
from ..common.utils import exec_cmd, confirm


class Widget(ABC):
    _activation: bool = False

    def activate(self):
        self._activation = True

    def deactivate(self):
        self._activation = False

    def is_activation(self):
        return self._activation

    @abstractmethod
    def _process_event(self):
        """Method of processing keyboard event.

        It will be instance in sub-class.
        """

    @abstractmethod
    def _render(self, size):
        """Method of render a widget.

        It will be instance in sub-class.
        """


class SwitchWidget(Widget):
    _activation: bool = True

    def __init__(self, sub_widgets: List = None, start_idx: int = 0):
        self.idx = start_idx

        if not sub_widgets:
            self.sub_widgets: List[Widget] = []
            self.sub_widgets_count = 0
        else:
            self.sub_widgets = sub_widgets
            self.sub_widgets_count = len(sub_widgets)

    def add(self, widget: Widget):
        """Add new sub widget."""
        self.sub_widgets.append(widget)
        self.sub_widgets_count += 1

    @property
    def current(self) -> int:
        return self.idx

    def set_current(self, idx: int):
        """Set the top sub widget, if index is valid."""
        if self.idx != idx and 0 <= idx < self.sub_widgets_count:
            self.sub_widgets[self.idx].deactivate()
            self.idx = idx
            self.sub_widgets[self.idx].activate()

    @abstractmethod
    def process_keyevent(self, key: str) -> Optional[int]:
        """Costom process keyboard event, instance in sub-class."""

    def _process_event(self, key: str):
        # If the result of process is int, then switch the page.
        # Else let current sub widget to process the key.
        next_idx = self.process_keyevent(key)
        if isinstance(next_idx, int):
            self.set_current(next_idx)
        else:
            self.sub_widgets[self.idx]._process_event(key)

    def _render(self, size):
        """
        This widget cannot render any, call current sub widget ``_render``
        """

        current_sub_widget = self.sub_widgets[self.idx]
        if not current_sub_widget.is_activation():
            current_sub_widget.activate()
        current_sub_widget._render(size)


class RowPanelWidget(Widget):
    def __init__(
        self,
        cursor: Optional[str] = None,
        help_wait: float = 1.5,
        widget: Widget = None,
        **kwargs: Any,
    ) -> None:
        self.widget = widget
        self.size = None

        self.cursor = "→" if not cursor or get_width(ord(cursor)) != 1 else cursor
        self.help_wait = help_wait

        # Initialize.
        self.cursor_row: int = 1
        self.display_range: List = None  # Allow display row range.

        self.extra = 0  # Extra occupied row.

        self.raw_data: List = None
        self.show_data: List = None

        self.update_raw: bool = False

        for key, value in kwargs.items():
            setattr(self, f"_ex_{key}", value)

    @abstractmethod
    def get_raw_data(self) -> List[Any]:
        """How to get the raw data."""

    def process_raw_data(self, raw_data: List[Any]) -> List[str]:
        return raw_data

    def generate_show_data(
        self, raw_data: List[str], width: int
    ) -> List[Tuple[str, int]]:
        """
        Process the raw data, and indicate the number of additional
        rows that need to be occupied when each piece of data is displayed.
        """

        new_list = []
        for line in raw_data:
            text = Style.plain(line)
            count = sum(get_width(ord(ch)) for ch in text)
            # [float] is to solve the division of python2 without
            # retaining decimal places.
            new_list.append((line, ceil(count / width) - 1))
        return new_list

    @abstractmethod
    def print_line(self, line: str, is_cursor_row: bool) -> None:
        """How to output one line.

        May has some different when current line is cursor line.
        Support to process cursor line specially.
        """

    def update(self):
        self.display_range = [1, self.size[1] - 1]
        self.raw_data: List[Any] = self.get_raw_data()
        self.show_data = self.generate_show_data(
            self.process_raw_data(self.raw_data), self.size[0]
        )

    def emit(self, name: str, cb: Optional[Callable] = None):
        if name == "update":
            self.update()

    def _render(self, size):
        if self.widget and self.widget.is_activation():
            self.widget._render(self.size)
            return
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
        self.extra: int = 0

        # Print needed display part.
        for index, item in enumerate(self.show_data, start=1):
            if self.display_range[0] <= index <= self.display_range[1] - self.extra:
                line, each_extra = item
                self.print_line(line, index == self.cursor_row)
                self.extra += each_extra

    def _process_event(self, key: str):
        if self.widget and self.widget.is_activation():
            # If has sub widget and it's activation.
            self.widget._process_event(key)
        elif self.is_activation():
            # Process key.
            if key in {"j", "down"}:
                # select pre file.
                self.cursor_row += 1
                self.cursor_row = min(self.cursor_row, len(self.show_data))

            elif key in {"k", "up"}:
                # select next file.
                self.cursor_row -= 1
                self.cursor_row = max(self.cursor_row, 1)

            elif key in {"J"}:
                # scroll down 5 lines.
                self.cursor_row += 5
                self.cursor_row = min(self.cursor_row, len(self.show_data))

            elif key in {"K"}:
                # scroll up 5 line
                self.cursor_row -= 5
                self.cursor_row = max(self.cursor_row, 1)

            elif key in {"?", "H"}:
                print(Term.clear_screen)
                print(
                    (
                        "k / ↑: select previous line.\n"
                        "j / ↓: select next line.\n"
                        "J: Scroll down 5 lines.\n"
                        "K: Scroll down 5 lines.\n"
                        "? / H : show help, wait {}s and exit.\n" + self.keyevent_help()
                    ).format(self.help_wait)
                )
                time.sleep(self.help_wait)

            else:
                #
                next_cursor = self.process_keyevent(key, self.cursor_row)
                if next_cursor is not None and 1 <= next_cursor <= len(self.show_data):
                    self.cursor_row = next_cursor

    @abstractmethod
    def process_keyevent(self, input_key: str, cursor_row: int) -> Optional[int]:
        """Handles keyboard events other than movement.

        Args:
            input_key (str): keyboard string.
            cursor_row (int): current line.
            data (Any): raw data.

        Returns:
            int: next cursor index.
        """

    def keyevent_help(self) -> str:
        """Get extra keyevent help message.

        Returns:
            str: help message string.
        """

        return ""


class ConfirmWidget:
    def __init__(self, msg: str, default: bool = True) -> None:
        self.msg = msg
        self.default = default

    def run(self):
        print(Term.clear_screen, end="")
        return confirm(self.msg, self.default)


class CmdRunner:
    def __init__(self, cmd: str, auto_run: bool = True, path: str = ".") -> None:
        self.cmd = cmd
        self.auto_run = auto_run
        self.run_path = path

        if self.auto_run:
            self.run()

    def run(self):
        print(Term.normal_screen)
        res_code = exec_cmd(self.cmd, cwd=self.run_path, reply=False)
        print(Term.alt_screen)
        return res_code
