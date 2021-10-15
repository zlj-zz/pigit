# -*- coding:utf-8 -*-


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
