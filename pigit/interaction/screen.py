# -*- coding:utf-8 -*-
from shutil import get_terminal_size
from webbrowser import get

from ..common import Term
from .util import TermSize


class Screen(object):
    def __init__(self, widget=None):
        self._widget = widget

        self._size = None

    def start(self):
        print(Term.alt_screen + Term.hide_cursor)
        self.render()  # first render.

    def end(self):
        print(Term.normal_screen + Term.show_cursor, end="")

    def __enter__(self):
        self.start()

    def __exit__(self, exc_type, exc_value, exc_tb):
        self.end()

    def init(self):
        self.render()

    def process_event(self, key: str):
        if key == "windows resize":
            self._size = None
        else:
            self._widget._process_event(key)

        self.render()

    def render(self, resize: bool = False):
        if not self._size:
            self._size = get_terminal_size()

        print(Term.clear_screen)  # Clear full screen and cursor goto top.
        self._widget._render(self._size)
