# -*- coding:utf-8 -*-
import re


class Fx(object):
    """Text effects
    * trans(string: str): Replace whitespace with escape move right to not
        overwrite background behind whitespace.
    * uncolor(string: str) : Removes all 24-bit color and returns string .
    """

    hide_cursor = "\033[?25l"  # * Hide terminal cursor
    show_cursor = "\033[?25h"  # * Show terminal cursor
    alt_screen = "\033[?1049h"  # * Switch to alternate screen
    normal_screen = "\033[?1049l"  # * Switch to normal screen
    clear_ = "\033[2J\033[0;0f"  # * Clear screen and set cursor to position 0,0
    # * Enable reporting of mouse position on click and release
    mouse_on = "\033[?1002h\033[?1015h\033[?1006h"
    mouse_off = "\033[?1002l"  # * Disable mouse reporting
    # * Enable reporting of mouse position at any movement
    mouse_direct_on = "\033[?1003h"
    mouse_direct_off = "\033[?1003l"  # * Disable direct mouse reporting

    start = "\033["  # * Escape sequence start
    sep = ";"  # * Escape sequence separator
    end = "m"  # * Escape sequence end
    # * Reset foreground/background color and text effects
    reset = rs = "\033[0m"
    bold = b = "\033[1m"  # * Bold on
    unbold = ub = "\033[22m"  # * Bold off
    dark = d = "\033[2m"  # * Dark on
    undark = ud = "\033[22m"  # * Dark off
    italic = i = "\033[3m"  # * Italic on
    unitalic = ui = "\033[23m"  # * Italic off
    underline = u = "\033[4m"  # * Underline on
    ununderline = uu = "\033[24m"  # * Underline off
    blink = bl = "\033[5m"  # * Blink on
    unblink = ubl = "\033[25m"  # * Blink off
    strike = s = "\033[9m"  # * Strike / crossed-out on
    unstrike = us = "\033[29m"  # * Strike / crossed-out off

    # * Precompiled regex for finding a 24-bit color escape sequence in a string
    color_re = re.compile(r"\033\[\d+;\d?;?\d*;?\d*;?\d*m")
    style_re = re.compile(r"\033\[\d+m")

    @staticmethod
    def trans(string):
        return string.replace(" ", "\033[1C")

    @classmethod
    def uncolor(cls, string):
        return cls.color_re.sub("", string)

    @classmethod
    def pure(cls, string):
        return cls.style_re.sub("", cls.uncolor(string))


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
    def to(line, col):
        # * Move cursor to line, column
        return "\033[{};{}f".format(line, col)

    @staticmethod
    def right(dx):
        return "\033[{}C".format(dx)

    @staticmethod
    def left(dx):
        return "\033[{}D".format(dx)

    @staticmethod
    def up(dy):
        return "\033[{}A".format(dy)

    @staticmethod
    def down(dy):
        return "\033[{}B".format(dy)

    save = "\033[s"  # * Save cursor position
    restore = "\033[u"  # * Restore saved cursor postion
    t = to
    r = right
    l = left
    u = up
    d = down

    @staticmethod
    def hide_cursor():
        print("\033[?25l")  # * Hide terminal cursor

    @staticmethod
    def show_cursor():
        print("\033[?25h")  # * Show terminal cursor
