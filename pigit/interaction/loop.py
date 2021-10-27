# -*- coding:utf-8 -*-
from typing import Callable
from ..keyevent import get_keyevent_obj


class LoopError(Exception):
    pass


class Loop(object):
    def __init__(self, screen=None, debug: bool = False):
        self.debug = debug

        if not screen:
            from .screen import Screen

            self._screen = Screen()
        else:
            self._screen = screen

        try:
            _keyevent_class = get_keyevent_obj()
        except Exception:
            raise LoopError("This behavior is not supported in the current system.")
        else:
            self._keyevent = _keyevent_class()

    def _loop(self):
        stopping: bool = False

        # self._screen.init()

        while not stopping:

            input_key = self._keyevent.sync_get_input()

            self._screen.process_event(input_key)

    def run(self):
        with self._screen:
            try:
                self._keyevent.signal_init()
                self._loop()
            except Exception:
                pass
            finally:
                self._keyevent.signal_restore()
