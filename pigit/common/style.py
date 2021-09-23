# -*- coding:utf-8 -*-

import sys
from typing import Tuple


class Color(object):
    """Holds representations for a 24-bit color value

    __init__(color, depth="fg", default=False)
        -- color accepts 6 digit hexadecimal: string "#RRGGBB", 2 digit
            hexadecimal: string "#FF" or decimal RGB "255 255 255" as a string.
        -- depth accepts "fg" or "bg"
    __call__(*args) joins str arguments to a string and apply color
    __str__ returns escape sequence to set color
    __iter__ returns iteration over red, green and blue in integer values of 0-255.

    * Values:
        .hexa: str
        .dec: Tuple[int, int, int]
        .red: int
        .green: int
        .blue: int
        .depth: str
        .escape: str
    """

    hexa: str
    dec: Tuple[int, int, int]
    red: int
    green: int
    blue: int
    depth: str
    escape: str
    default: bool

    TRUE_COLOR = sys.version_info < (3, 0)

    def __init__(self, color, depth="fg", default=False):
        self.depth = depth
        self.default = default
        try:
            if not color:
                self.dec = (-1, -1, -1)
                self.hexa = ""
                self.red = self.green = self.blue = -1
                self.escape = "\033[49m" if depth == "bg" and default else ""
                return

            elif color.startswith("#"):
                self.hexa = color
                if len(self.hexa) == 3:
                    self.hexa += self.hexa[1:3] + self.hexa[1:3]
                    c = int(self.hexa[1:3], base=16)
                    self.dec = (c, c, c)
                elif len(self.hexa) == 7:
                    self.dec = (
                        int(self.hexa[1:3], base=16),
                        int(self.hexa[3:5], base=16),
                        int(self.hexa[5:7], base=16),
                    )
                else:
                    raise ValueError(
                        "Incorrectly formatted hexadecimal rgb string: {}".format(
                            self.hexa
                        )
                    )

            else:
                c_t = tuple(map(int, color.split(" ")))
                if len(c_t) == 3:
                    self.dec = c_t  # type: ignore
                else:
                    raise ValueError('RGB dec should be "0-255 0-255 0-255"')

            ct = self.dec[0] + self.dec[1] + self.dec[2]
            if ct > 255 * 3 or ct < 0:
                raise ValueError("RGB values out of range: {}".format(color))
        except Exception:
            # errlog.exception(str(e))
            self.escape = ""
            return

        if self.dec and not self.hexa:
            self.hexa = "%s%s%s" % (
                hex(self.dec[0]).lstrip("0x").zfill(2),
                hex(self.dec[1]).lstrip("0x").zfill(2),
                hex(self.dec[2]).lstrip("0x").zfill(2),
            )

        if self.dec and self.hexa:
            self.red, self.green, self.blue = self.dec
            self.escape = "\033[%s;2;%sm" % (
                38 if self.depth == "fg" else 48,
                ";".join(str(c) for c in self.dec),
            )

        if Color.TRUE_COLOR:
            self.escape = "{}".format(
                self.truecolor_to_256(rgb=self.dec, depth=self.depth)
            )

    def __str__(self):
        return self.escape

    def __repr__(self):
        return repr(self.escape)

    def __iter__(self):
        for c in self.dec:
            yield c

    # def __call__(self, *args: str) -> str:
    #     if len(args) < 1:
    #         return ""
    #     return f'{self.escape}{"".join(args)}{getattr(Term, self.depth)}'

    @staticmethod
    def truecolor_to_256(rgb, depth="fg"):
        out = ""
        pre = "\033[{};5;".format("38" if depth == "fg" else "48")

        greyscale = (rgb[0] // 11, rgb[1] // 11, rgb[2] // 11)
        if greyscale[0] == greyscale[1] == greyscale[2]:
            out = "{}{}m".format(pre, 232 + greyscale[0])
        else:
            out = "{}{}m".format(
                pre,
                round(rgb[0] / 51) * 36
                + round(rgb[1] / 51) * 6
                + round(rgb[2] / 51)
                + 16,
            )

        return out

    @staticmethod
    def escape_color(hexa="", r=0, g=0, b=0, depth="fg"):
        """Returns escape sequence to set color
        * accepts either 6 digit hexadecimal hexa="#RRGGBB", 2 digit hexadecimal: hexa="#FF"
        * or decimal RGB: r=0-255, g=0-255, b=0-255
        * depth="fg" or "bg"
        """
        dint = 38 if depth == "fg" else 48
        color = ""
        if hexa:
            try:
                if len(hexa) == 3:
                    c = int(hexa[1:], base=16)
                    if Color.TRUE_COLOR:
                        color = "\033[{};2;{};{};{}m".format(dint, c, c, c)
                    else:
                        color = Color.truecolor_to_256(rgb=(c, c, c), depth=depth)
                elif len(hexa) == 7:
                    if Color.TRUE_COLOR:
                        color = "\033[{};2;{};{};{}m".format(
                            dint,
                            int(hexa[1:3], base=16),
                            int(hexa[3:5], base=16),
                            int(hexa[5:7], base=16),
                        )
                    else:
                        color = "{}".format(
                            Color.truecolor_to_256(
                                rgb=(
                                    int(hexa[1:3], base=16),
                                    int(hexa[3:5], base=16),
                                    int(hexa[5:7], base=16),
                                ),
                                depth=depth,
                            )
                        )
            except ValueError:
                # errlog.exception(f'{e}')
                pass
        else:
            if Color.TRUE_COLOR:
                color = "\033[{};2;{};{};{}m".format(dint, r, g, b)
            else:
                color = "{}".format(Color.truecolor_to_256(rgb=(r, g, b), depth=depth))
        return color

    @classmethod
    def fg(cls, *args):
        if len(args) > 2:
            return cls.escape_color(r=args[0], g=args[1], b=args[2], depth="fg")
        else:
            return cls.escape_color(hexa=args[0], depth="fg")

    @classmethod
    def bg(cls, *args):
        if len(args) > 2:
            return cls.escape_color(r=args[0], g=args[1], b=args[2], depth="bg")
        else:
            return cls.escape_color(hexa=args[0], depth="bg")


class Symbol(object):
    # yapf: disable
    rune:dict[str,list[str]] = {
        "normal":        ["-", "|", "|", "|", "|", "|", "|", "|", "-", "-", "-"],
        "normal_double": ["=", "‖", "‖", "‖", "‖", "‖", "‖", "‖", "=", "=", "="],
        "fine":          ["─", "│", "╭", "╮", "╰", "╯", "├", "┤", "┬", "┴", "┼"],
        "radian":        ["─", "│", "┌", "┐", "└", "┘", "├", "┤", "┬", "┴", "┼"],
        "bold":     ["━", "┃", "┏", "┓", "┗", "┛", "┣", "┫", "┳", "┻", "╋"],
        "double":   ["═", "║", "╔", "╗", "╚", "╝", "╠", "╣", "╦", "╩", "╬"],
    }

    normal_rune: list[str] = ["-", "|", "|", "|", "|", "|", "|", "|", "-", "-", "-"]
    normal_double_rune: list[str] = ["=", "‖", "‖", "‖", "‖", "‖", "‖", "‖", "=", "=", "="]
    fine_rune: list[str] = ["─", "│", "╭", "╮", "╰", "╯", "├", "┤", "┬", "┴", "┼"]
    radian_rune: list[str] = ["─", "│", "┌", "┐", "└", "┘", "├", "┤", "┬", "┴", "┼"]
    bold_rune: list[str] = ["━", "┃", "┏", "┓", "┗", "┛", "┣", "┫", "┳", "┻", "╋"]
    double_rune: list[str] = ["═", "║", "╔", "╗", "╚", "╝", "╠", "╣", "╦", "╩", "╬"]
    # yapf: enable
