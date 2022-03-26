# -*- coding:utf-8 -*-

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .screen import Screen


class ExitEventLoop(Exception):
    """Get to exit current event loop."""


class EventLoop(object):
    """
    Params:
        screen (Screen): screen to use, default is a new :class:`.screen.Screen`.
        input_handle (Input): input handle to use, default is a new :class:`.input:PosixInput`.
        real_time (bool): whether refresh screen real time.
    """

    def __init__(
        self,
        screen: "Screen" = None,
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
            # XXX: now not support windows.
            from .input import PosixInput, is_mouse_event

            input_handle = PosixInput()
            # adjust the input whether is a mouse event.
            self.is_mouse_event = is_mouse_event
        self._input_handle = input_handle

    def set_input_timeouts(self, timeout: float):
        self._input_handle.set_input_timeouts(timeout)

    def _loop(self):
        """Main loop"""
        if input_key := self._input_handle.get_input():
            first_one = input_key[0]

            if first_one == "window resize":
                self._screen.resize()
            elif hasattr(self, "is_mouse_event") and self.is_mouse_event(first_one):
                self._screen.process_mouse(first_one)
            else:
                self._screen.process_input(first_one)
        elif self._real_time:
            self._screen.render()

    def _run(self):
        try:
            while True:
                self._loop()
        except (ExitEventLoop, KeyboardInterrupt, EOFError):
            self._input_handle.stop()

    def run(self):
        with self._screen:
            self._input_handle.start()
            self._run()
