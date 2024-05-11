import sys
from shutil import get_terminal_size
from typing import List, Tuple


def _stdout(*values, sep: str = "", end: str = ""):
    """Output values to screen."""
    sys.stdout.write(sep.join(values) + end)
    sys.stdout.flush()


class Signal:
    hide_cursor = "\033[?25l"  # * Hide terminal cursor
    show_cursor = "\033[?25h"  # * Show terminal cursor
    alt_screen = "\033[?1049h"  # * Switch to alternate screen
    normal_screen = "\033[?1049l"  # * Switch to normal screen
    clear_screen = "\033[2J\033[0;0f"  # * Clear screen and set cursor to position 0,0

    # * Enable reporting of mouse position on click and release
    mouse_on = "\033[?1002h\033[?1015h\033[?1006h"
    mouse_off = "\033[?1002l"  # * Disable mouse reporting

    # * Enable reporting of mouse position at any movement
    mouse_direct_on = "\033[?1003h"
    mouse_direct_off = "\033[?1003l"  # * Disable direct mouse reporting

    term_space = " "


class Term:
    def to_alt_screen(self):
        _stdout(Signal.alt_screen + Signal.hide_cursor)

    def to_normal_screen(self):
        _stdout(Signal.normal_screen + Signal.show_cursor)

    def clear_screen(self):
        _stdout(Signal.clear_screen)  # Clear full screen and cursor goto top.

    def get_term_size(self):
        return get_terminal_size()


class Cursor:
    """Class with collection of cursor movement functions:
    Functions:
        .t[o](line, column)
        .r[ight](columns)
        .l[eft](columns)
        .u[p](lines)
        .d[own](lines)
        .save()
        .restore()
    """

    @staticmethod
    def to(row: int, col: int):
        # * Move cursor to line, column
        return _stdout(f"\033[{row};{col}f")

    @staticmethod
    def right(dx: int):
        return _stdout(f"\033[{dx}C")

    @staticmethod
    def left(dx: int):
        return _stdout(f"\033[{dx}D")

    @staticmethod
    def up(dy: int):
        return _stdout(f"\033[{dy}A")

    @staticmethod
    def down(dy: int):
        return _stdout(f"\033[{dy}B")

    save = "\033[s"  # * Save cursor position
    restore = "\033[u"  # * Restore saved cursor position
    t = to
    r = right
    l = left
    u = up
    d = down

    @staticmethod
    def hide_cursor():
        print("\033[?25l", end="")  # * Hide terminal cursor

    @staticmethod
    def show_cursor():
        print("\033[?25h", end="")  # * Show terminal cursor


class Render:
    @classmethod
    def clear_screen(cls):
        _stdout("\033[2J\033[0;0f")
        Cursor.to(1, 1)

    @classmethod
    def draw(cls, content: List[str], x: int, y: int, size: Tuple[int, int]) -> None:
        """Draw content to screen. Using by component."""
        col, row = size

        cur_x = x
        for line in content:
            # clear line
            Cursor.to(cur_x, y)
            _stdout(Signal.term_space * col)
            # write new line
            Cursor.to(cur_x, y)
            _stdout(line)

            cur_x += 1

        while cur_x <= row:
            Cursor.to(cur_x, y)
            _stdout(Signal.term_space * col)

            cur_x += 1
