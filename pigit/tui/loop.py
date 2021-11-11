# -*- coding:utf-8 -*-
from typing import Callable
from ..keyevent import KeyEventHookError


class ExitLoop(Exception):
    pass


class Loop(object):
    def __init__(self, screen=None, key_handle=None, debug: bool = False):
        self.debug = debug

        # Init screen object.
        if not screen:
            from .screen import Screen

            screen = Screen()
        self._screen = screen

        # Init keyboard handle object.
        if not key_handle:
            from ..keyevent import get_keyevent_obj, KeyEventHookError

            try:
                _keyevent_class = get_keyevent_obj()
            except Exception:
                raise ExitLoop("This behavior is not supported in the current system.")
            else:
                key_handle = _keyevent_class()
        self._keyevent = key_handle

    def _loop(self):
        input_key = self._keyevent.sync_get_input()
        # XXX:split keypress and mouse (current only has keypress)

        self._screen.process_event(input_key)

    def _run(self):
        with self._screen:
            try:
                self._keyevent.signal_init()
                self._did_something = True
                while True:
                    self._loop()
            except KeyEventHookError:
                pass
            finally:
                self._keyevent.signal_restore()

    def run(self):
        try:
            self._run()
        except ExitLoop:
            pass
