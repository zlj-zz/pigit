# -*- coding:utf-8 -*-
from shutil import get_terminal_size

from ..common import Term
from .util import TermSize


class Screen(object):
    def __init__(self, widget=None):
        self._widget = widget

        self.update_size()

    def update_size(self):
        self.width, self.height = get_terminal_size()
        print(self.width)
        TermSize.set(self.width, self.height)
        # TermSize.width = self.width
        # TermSize.height = self.height
        print(TermSize.width)

    def start(self):
        print(Term.alt_screen + Term.hide_cursor)
        self.render()  # frist render.

    def end(self):
        print(Term.normal_screen + Term.show_cursor, end="")

    def __enter__(self):
        self.start()

    def __exit__(self, exc_type, exc_value, exc_tb):
        self.end()

    def init(self):
        self.render()

    def process_event(self, key: str):
        if key == "window resize":
            self.update_size()
        else:
            self._widget._process_event(key)

        self.render()

    def render(self, resize: bool = False):
        print(Term.clear_screen)  # Clear full screen and cursor goto top.
        self._widget._render()
