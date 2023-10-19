import sys
from shutil import get_terminal_size
from typing import TYPE_CHECKING, List, Optional, Tuple

from pigit.ext.log import logger

from .console import Signal, Cursor

if TYPE_CHECKING:
    from .components import Component


class Screen(Signal):
    """Open a new terminal screen.

    Params:
        widget (Widget): main widget be needed by screen.
        alt_screen (bool): whether switch to a new screen.

    Attributes:
        _size (tuple): the terminal can be using size (width, height).
    """

    def __init__(self, widget: "Component", alt: bool = True):
        self._widget = widget
        self._alt = alt

        self._size: Optional[Tuple[int, int]] = get_terminal_size()

        self.cursor = Cursor

    def stdout(self, *values, sep: str = "", end: str = ""):
        """Output values to screen."""
        sys.stdout.write(sep.join(values) + end)
        sys.stdout.flush()

    def start(self):
        if self._alt:
            self.stdout(self.alt_screen + self.hide_cursor)

        self.resize()  # include render.

    def stop(self):
        if self._alt:
            self.stdout(self.normal_screen + self.show_cursor)

    def __enter__(self):
        self.start()

    def __exit__(self, exc_type, exc_value, exc_tb):
        self.stop()

    def resize(self):
        """When the size has changed, this method will be call by `.loop.Loop` and try to render again."""
        self._size = get_terminal_size()
        self._widget.resize(self._size)
        self.render()

    def draw(self, content: List[str], x: int, y: int, size: Tuple[int, int]):
        """Draw content to screen. Using by component."""
        for i, line in enumerate(content, start=0):
            logger(__name__).debug((x + i, y))
            self.stdout(self.cursor.to(x + i, y))
            self.stdout(line)

    def process_input(self, key: str):
        self._widget._handle_event(key)

    def process_mouse(self, mouse):
        # TODO: need finish.
        pass

    def render(self, resize: bool = False):
        self.stdout(Signal.clear_screen)  # Clear full screen and cursor goto top.
        self._widget._render(self)
