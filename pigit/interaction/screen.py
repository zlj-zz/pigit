# -*- coding:utf-8 -*-
from shutil import get_terminal_size

from ..common import Term, Fx, exec_cmd, shorten, get_width, render_str
from .util import TermSize


class Screen(object):
    def __init__(self, widget=None):
        self._widget = widget

        self.resize()

    def resize(self):
        self.width, self.height = get_terminal_size()
        TermSize.set(self.width, self.height)

    def start(self):
        print(Term.alt_screen + Term.hide_cursor)
        self.render()  # frist render.

    def end(self):
        print(Term.normal_screen + Term.show_cursor, end="")

    def __enter__(self):
        self.start()

    def __exit__(self, exc_type, exc_value, exc_tb):
        self.end()

    def process_key(self, key: str):
        pass

    def render(self, resize: bool = False):
        pass
