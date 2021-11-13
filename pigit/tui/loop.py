# -*- coding:utf-8 -*-
from typing import Callable


class ExitLoop(Exception):
    pass


class Loop(object):
    def __init__(
        self,
        screen=None,
        input_handle=None,
        real_time: bool = False,
        debug: bool = False,
    ):
        self._real_time = real_time
        self.debug = debug

        # Init screen object.
        if not screen:
            from .screen import Screen

            screen = Screen()
        self._screen = screen

        # Init keyboard handle object.
        if not input_handle:
            """
            from .keyevent import get_keyevent_obj, KeyEventHookError

            try:
                _keyevent_class = get_keyevent_obj()
            except Exception:
                raise ExitLoop("This behavior is not supported in the current system.")
            else:
                input_handle = _keyevent_class()
            """
            from .input import PosixInput, is_mouse_event

            self.is_mouse_event = is_mouse_event
            input_handle = PosixInput()
        self._input_handle = input_handle

    def set_input_timeouts(self, timeout):
        self._input_handle.set_input_timeouts(timeout)

    def _loop(self):
        input_key = self._input_handle.get_input()

        if input_key:
            first_one = input_key[0]

            if first_one == "window resize":
                self._screen.resize()
            elif hasattr(self, "is_mouse_event") and self.is_mouse_event(first_one):
                self._screen.process_mouse(first_one)
            else:
                self._screen.process_input(first_one)
        else:
            if self._real_time:
                self._screen.render()

    def _run(self):
        with self._screen:
            self._input_handle.start()
            try:
                while True:
                    self._loop()
            except (ExitLoop, KeyboardInterrupt):
                self._input_handle.stop()

    def run(self):
        self._run()
