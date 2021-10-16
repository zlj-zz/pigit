# -*- coding:utf-8 -*-

import sys
import re
import logging
from typing import Tuple, Union, Match

Log = logging.getLogger(__name__)


COLOR_CODE = {
    "light_pink": "#FFB6C1",
    "pink": "#FFC0CB",
    "crimson": "#DC143C",
    "lavender_blush": "#FFF0F5",
    "pale_violet_red": "#DB7093",
    "hot_pink": "#FF69B4",
    "deep_pink": "#FF1493",
    "medium_violet_red": "#C71585",
    "orchid": "#DA70D6",
    "thistle": "#D8BFD8",
    "plum": "#DDA0DD",
    "violet": "#EE82EE",
    "magenta": "#FF00FF",
    "fuchsia": "#FF00FF",
    "dark_magenta": "#8B008B",
    "purple": "#800080",
    "medium_orchid": "#BA55D3",
    "dark_violet": "#9400D3",
    "dark_orchid": "#9932CC",
    "indigo": "#4B0082",
    "blue_violet": "#8A2BE2",
    "medium_purple": "#9370DB",
    "medium_slateBlue": "#7B68EE",
    "slate_blue": "#6A5ACD",
    "dark_slate_blue": "#483D8B",
    "lavender": "#E6E6FA",
    "ghost_white": "#F8F8FF",
    "blue": "#0000FF",
    "medium_blue": "#0000CD",
    "midnight_blue": "#191970",
    "dark_blue": "#00008B",
    "navy": "#000080",
    "royal_blue": "#4169E1",
    "cornflower_blue": "#6495ED",
    "light_steel_blue": "#B0C4DE",
    "light_slate_gray": "#778899",
    "slate_gray": "#708090",
    "dodder_blue": "#1E90FF",
    "alice_blue": "#F0F8FF",
    "steel_blue": "#4682B4",
    "light_sky_blue": "#87CEFA",
    "sky_blue": "#87CEEB",
    "deep_sky_blue": "#00BFFF",
    "light_blue": "#ADD8E6",
    "powder_blue": "#B0E0E6",
    "cadet_blue": "#5F9EA0",
    "azure": "#F0FFFF",
    "light_cyan": "#E1FFFF",
    "pale_turquoise": "#AFEEEE",
    "cyan": "#00FFFF",
    "aqua": "#D4F2E7",
    "dark_turquoise": "#00CED1",
    "dark_slate_gray": "#2F4F4F",
    "dark_cyan": "#008B8B",
    "teal": "#008080",
    "medium_turquoise": "#48D1CC",
    "light_sea_green": "#20B2AA",
    "turquoise": "#40E0D0",
    "aquamarine": "#7FFFAA",
    "medium_aquamarine": "#00FA9A",
    "medium_spring_green": "#00FF7F",
    "mint_cream": "#F5FFFA",
    "spring_green": "#3CB371",
    "sea_green": "#2E8B57",
    "honeydew": "#F0FFF0",
    "light_green": "#90EE90",
    "pale_green": "#98FB98",
    "ok": "#98FB98",
    "good": "#98FB98",
    "right": "#98FB98",
    "dark_sea_green": "#8FBC8F",
    "lime_green": "#32CD32",
    "lime": "#00FF00",
    "forest_green": "#228B22",
    "green": "#008000",
    "dark_green": "#006400",
    "chartreuse": "#7FFF00",
    "lawn_green": "#7CFC00",
    "green_yellow": "#ADFF2F",
    "olive_drab": "#556B2F",
    "beige": "#F5F5DC",
    "light_goldenrod_yellow": "#FAFAD2",
    "ivory": "#FFFFF0",
    "light_yellow": "#FFFFE0",
    "yellow": "#FFFF00",
    "olive": "#808000",
    "dark_khaki": "#BDB76B",
    "lemon_chiffon": "#FFFACD",
    "pale_goldenrod": "#EEE8AA",
    "khaki": "#F0E68C",
    "gold": "#FFD700",
    "cornsilk": "#FFF8DC",
    "goldenrod": "#DAA520",
    "floral_white": "#FFFAF0",
    "old_lace": "#FDF5E6",
    "wheat": "#F5DEB3",
    "moccasin": "#FFE4B5",
    "orange": "#FFA500",
    "papaya_whip": "#FFEFD5",
    "blanched_almond": "#FFEBCD",
    "navajo_white": "#FFDEAD",
    "antique_white": "#FAEBD7",
    "tan": "#D2B48C",
    "burly_wood": "#DEB887",
    "bisque": "#FFE4C4",
    "dark_orange": "#FF8C00",
    "linen": "#FAF0E6",
    "peru": "#CD853F",
    "peach_puff": "#FFDAB9",
    "sandy_brown": "#F4A460",
    "chocolate": "#D2691E",
    "saddle_brown": "#8B4513",
    "sea_shell": "#FFF5EE",
    "sienna": "#A0522D",
    "light_salmon": "#FFA07A",
    "coral": "#FF7F50",
    "orange_red": "#FF4500",
    "dark_salmon": "#E9967A",
    "tomato": "#FF6347",
    "bad": "#FF6347",
    "error": "#FF6347",
    "misty_rose": "#FFE4E1",
    "salmon": "#FA8072",
    "snow": "#FFFAFA",
    "light_coral": "#F08080",
    "rosy_brown": "#BC8F8F",
    "indian_red": "#CD5C5C",
    "red": "#FF0000",
    "brown": "#A52A2A",
    "fire_brick": "#B22222",
    "dark_red": "#8B0000",
    "maroon": "#800000",
    "white": "#FFFFFF",
    "white_smoke": "#F5F5F5",
    "bright_gray": "#DCDCDC",
    "light_grey": "#D3D3D3",
    "silver": "#C0C0C0",
    "dark_gray": "#A9A9A9",
    "gray": "#808080",
    "dim_gray": "#696969",
    "black": "#000000",
}

FX_CODE = {
    "b": "\033[1m",
    "u": "\033[4m",
    "i": "\033[3m",
    "bl": "\033[5m",
    "bold": "\033[1m",
    "underline": "\033[4m",
    "italic": "\033[3m",
    "blink": "\033[5m",
}


class Fx(object):
    """Text effects
    * trans(string: str): Replace whitespace with escape move right to not
        overwrite background behind whitespace.
    * uncolor(string: str) : Removes all 24-bit color and returns string .
    * pure(string: str): Removes all style string.

    Docs test
        >>> txt = '\033[49;1;20m\033[1mhello word!\033[0m'
        >>> Fx.pure(txt)
        'hello word!'

    """

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


class Color(object):
    """Holds representations for a 24-bit color value

    __init__(color, depth="fg", default=False)
        : color accepts 6 digit hexadecimal: string "#RRGGBB", 2 digit
            hexadecimal: string "#FF" or decimal RGB "255 255 255" as a string.
        : depth accepts "fg" or "bg"
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

    def __init__(self, color, depth="fg", default=False) -> None:
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
        except Exception as e:
            Log.error(str(e) + str(e.__traceback__))
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
            self.escape = self.truecolor_to_256(rgb=self.dec, depth=self.depth)

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
    def truecolor_to_256(rgb, depth="fg") -> str:
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
    def escape_color(hexa="", r=0, g=0, b=0, depth="fg") -> str:
        """Returns escape sequence to set color

        Args:
            hexa (str): accepts either 6 digit hexadecimal hexa="#RRGGBB",
                        2 digit hexadecimal: hexa="#FF".
            r (int): 0-255, the r of decimal RGB.
            g (int): 0-255, the g of decimal RGB.
            b (int): 0-255, the b of decimal RGB.

        Returns:
            color (str): ascii color code.
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
                color = Color.truecolor_to_256(rgb=(r, g, b), depth=depth)
        return color

    @classmethod
    def fg(cls, *args) -> str:
        if len(args) > 2:
            return cls.escape_color(r=args[0], g=args[1], b=args[2], depth="fg")
        else:
            return cls.escape_color(hexa=args[0], depth="fg")

    @classmethod
    def bg(cls, *args) -> str:
        if len(args) > 2:
            return cls.escape_color(r=args[0], g=args[1], b=args[2], depth="bg")
        else:
            return cls.escape_color(hexa=args[0], depth="bg")

    @classmethod
    def by_name(cls, name: str, depth: str = "fg"):
        """Get color ascii code by support color name."""

        color_hexa = COLOR_CODE.get(name, "")

        if not color_hexa:
            return color_hexa

        if depth == "fg":
            return cls.fg(color_hexa)
        elif depth == "bg":
            return cls.bg(color_hexa)
        else:
            return ""


# color hexa string reg.
_color_re = re.compile(r"^#[0-9A-Fa-f]{6}")


def is_color(code: Union[str, list, tuple]) -> bool:
    """Adjust whether is color. Like: '#FF0000', [255, 0, 0], (0, 255, 0)

    Test `is_color()` whether can right adjust.

        >>> is_color('#FF0000')
        True
        >>> is_color('sky_blue')
        True
        >>> is_color([255, 0, 0])
        True
        >>> is_color((0, 256, 0))
        False
        >>> is_color(None)
        False
        >>> is_color(12345)
        False

    """

    if type(code) == str:
        return (
            _color_re.match(str(code)) is not None
            or COLOR_CODE.get(code, None) is not None
        )
    elif isinstance(code, list) or isinstance(code, tuple):
        return len(code) == 3 and not bool([i for i in code if i < 0 or i > 255])
    else:
        return False


# If has special format string, will try to render the color and font style.
# If cannot to render the string will keep it.
#
# .+--------------------------------> font style prefix (options).
#  |         +----------------------> the content being rendered.
#  |         |             +--------> color code or color name, like: blue (options).
#  |         |             |
#  b`This is a string.`<#FF0000>
#
# Must keep has one of font style or color for making sure can right render.
# If ignore the two both, it will do nothing.
# Only '`' with consecutive beginning and ending will be considered part of the content.
def render_style(
    _msg: str,
    /,
    *,
    _color_sub=re.compile(
        r"(([a-z]+)?`(`*.*?`*)`(?:<([a-zA-Z_]+|#[0-9a-fA-F]{6})>)?)"
    ).sub,
):
    get_color = COLOR_CODE.__getitem__
    get_fx = FX_CODE.__getitem__

    def do_replace(match: Match[str]) -> str:
        raw, fx, content, color_code = match.groups()
        # print(raw, fx, content, color_code)

        if not color_code and not fx:
            return raw
        else:
            try:
                # No fx then get empty.
                font_style = get_fx(fx) if fx else ""

                # Get color hexa.
                if color_code:
                    color_hexa = (
                        color_code
                        if color_code.startswith("#")
                        else get_color(color_code)
                    )
                else:
                    color_hexa = ""

                color_style = Color.fg(color_hexa) if color_hexa else ""

                return font_style + color_style + content + "\033[0m"
            except KeyError:
                return raw

    return _color_sub(do_replace, _msg)


class BoxSymbol(object):
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


if __name__ == "__main__":
    import doctest

    doctest.testmod(verbose=True)

    txt1 = "Today is a b`nice` `day`<green>."
    print(render_style(txt1))

    txt1 = "Today is a b`nice`<#FF0000> day."
    # print(render_style(txt1))

    txt2 = "Today is a `nice`<sky_blue> day."
    # print(render_style(txt2))

    txt2 = "Today is a b```nice``` day."
    print(render_style(txt2))

    txt2 = "Today is a `nice`xxxxxxx day."
    print(render_style(txt2))

    txt2 = "Today is a `nice`<xxxxxxx> day."
    print(render_style(txt2))

    print(render_style("i`Don't found Git, maybe need install.`tomato"))
