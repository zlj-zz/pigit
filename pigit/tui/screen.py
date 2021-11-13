# -*- coding:utf-8 -*-
from shutil import get_terminal_size

from .console import Term


class Screen(object):
    def __init__(self, widget=None, alt_screen: bool = True):
        self._widget = widget
        self._alt_screen = alt_screen

        self._size = None

    def start(self):
        if self._alt_screen:
            print(Term.alt_screen + Term.hide_cursor, end="")
        self.render()  # first render.

    def stop(self):
        if self._alt_screen:
            print(Term.normal_screen + Term.show_cursor, end="")

    def __enter__(self):
        self.start()

    def __exit__(self, exc_type, exc_value, exc_tb):
        self.stop()

    def resize(self):
        self._size = None
        self.render()

    def process_input(self, key: str):
        self._widget._process_event(key)
        self.render()

    def process_mouse(self, mouse):
        # TODO: need finish.
        pass

    def render(self, resize: bool = False):
        if not self._size:
            self._size = get_terminal_size()

        print(Term.clear_screen)  # Clear full screen and cursor goto top.
        self._widget._render(self._size)
