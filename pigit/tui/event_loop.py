from typing import TYPE_CHECKING, List, Optional, Tuple

from .console import Render, Signal, Term

if TYPE_CHECKING:
    from .components import Component
    from .input import InputTerminal


class ExitEventLoop(Exception):
    """Get to exit current event loop."""


class EventLoop(Term):
    BINDINGS: Optional[List[Tuple[str, str]]] = None

    def __init__(
        self,
        child: "Component",
        input_handle: Optional["InputTerminal"] = None,
        real_time: bool = False,
        alt: bool = True,
    ) -> None:
        self._render = Render

        self._child = child
        self._real_time = real_time

        # Init keyboard handle object.
        if not input_handle:
            # XXX: now not support windows.
            from .input import PosixInput, is_mouse_event

            input_handle = PosixInput()
            # adjust the input whether is a mouse event.
            self.is_mouse_event = is_mouse_event
        self._input_handle = input_handle
        self._alt = alt

        self._event_map = {}
        if self.BINDINGS is not None:
            for ev in self.BINDINGS:
                self._event_map[ev[0]] = ev[1]

    def start(self):
        if self._alt:
            self.to_alt_screen()

        self.resize()  # include render.

    def stop(self):
        if self._alt:
            self.to_normal_screen()

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_value, exc_tb):
        self.stop()

    def resize(self) -> None:
        """When the size has changed, this method will be call by `.loop.Loop` and try to render again."""
        self._size = self.get_term_size()
        self._child.resize(self._size)
        self.render()

    def render(self) -> None:
        self.clear_screen()
        self._child._render()

    def set_input_timeouts(self, timeout: float) -> None:
        self._input_handle.set_input_timeouts(timeout)

    def _loop(self) -> None:
        """Main loop"""
        while True:
            if (input_key := self._input_handle.get_input()) and input_key[0]:
                first_one: str = input_key[0][0]

                tg_name = self._event_map.get(first_one)
                tg_fn = None if tg_name is None else getattr(self, tg_name, None)

                if callable(tg_fn):  # sourcery skip: remove-pass-elif
                    tg_fn()
                elif first_one == "window resize":
                    self.resize()
                elif hasattr(self, "is_mouse_event") and self.is_mouse_event(first_one):
                    # self._child.process_mouse(first_one)
                    pass
                else:  # default is keyboard event.
                    self._child._handle_event(first_one)
            elif self._real_time:
                self._child.render()

    def run(self) -> None:
        try:
            self.start()
            self._input_handle.start()
            self._loop()
        except (ExitEventLoop, KeyboardInterrupt, EOFError):
            self._input_handle.stop()
            self.stop()
        except Exception as e:
            self._input_handle.stop()
            self.stop()
            print(e, e.__traceback__)

    def quit(self) -> None:
        raise ExitEventLoop("Quit")
