# -*- coding:utf-8 -*-

from typing import List, Literal, Optional, Tuple, Union, Match
import sys, re

from .errors import ColorError, StyleSyntaxError


COLOR_CODE = {
    "nocolor": "",
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

ColorType = Union[str, List, Tuple]
ColorDepthType = Literal["fg", "bg"]

# color hexa string reg.
_COLOR_RE = re.compile(r"^#([0-9A-Fa-f]{6}|[0-9A-Fa-f]{2})$")

# If has special format string, will try to render the color and font style.
# If cannot to render the string will keep it.
#
# .+-----------------------------------> font style prefix (options).
#  |         +-------------------------> the content being rendered.
#  |         |             +-----------> color code or color name, like: blue (options).
#  |         |             |       +---> background color code.
#  |         |             |       |
#  |         |             |       |
#  b`This is a string.`<#FF0000,#00FF00>
#
# Must keep has one of font style or color for making sure can right render.
# If ignore the two both, it will do nothing.
# Only '`' with consecutive beginning and ending will be considered part of the content.
_STYLE_RE = re.compile(
    r"(([a-z]+|\((?:[a-z\s],?)+\))?`(`*.*?`*)`(?:<([a-zA-Z_]+|#[0-9a-fA-F]{6})?(?:,([a-zA-Z_]+|#[0-9a-fA-F]{6}))?>)?)",
    re.M | re.S,  # allow multi lines.
)


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

    supports = {
        "bold": "bold",
        "b": "bold",
        "dark": "dark",
        "d": "dark",
        "italic": "italic",
        "i": "italic",
        "underline": "underline",
        "u": "underline",
        "strike": "strike",
        "s": "strike",
        "blink": "blink",
    }

    code_map = {
        0: "1",
        1: "2",
        2: "3",
        3: "4",
        4: "5",
        5: "9",
    }

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

    @classmethod
    def by_name(cls, name: str) -> str:
        try:
            fx_code = getattr(cls, name)
        except AttributeError:
            fx_code = ""

        return fx_code


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
    rgb: Tuple[int, int, int]
    red: int
    green: int
    blue: int
    depth: str
    escape: str
    default: bool

    TRUE_COLOR = sys.version_info < (3, 0)

    def __init__(
        self,
        color: Optional[ColorType] = None,
        depth: ColorDepthType = "fg",
        default: bool = False,
    ) -> None:
        self.depth = depth
        self.default = default

        if not color:
            self.rgb = (-1, -1, -1)
            self.hexa = ""
            self.red = self.green = self.blue = -1
            self.escape = "\033[49m" if depth == "bg" and default else ""
            return

        if not self.is_color(color):
            raise ColorError("Not valid color.") from None

        if isinstance(color, str):
            self.rgb = rgb = self.generate_rgb(color)
            self.hexa = color
        else:  # list or tuple
            self.rgb = rgb = color
            self.hexa = "#%s%s%s" % (
                hex(rgb[0]).lstrip("0x").zfill(2),
                hex(rgb[1]).lstrip("0x").zfill(2),
                hex(rgb[2]).lstrip("0x").zfill(2),
            )

        self.escape = self.escape_color(r=rgb[0], g=rgb[1], b=rgb[2], depth=depth)

    def __str__(self):
        return self.escape

    def __repr__(self):
        return repr(self.escape)

    def __iter__(self):
        yield from self.rgb

    @staticmethod
    def generate_rgb(hexa: str) -> Tuple:
        hexa_len = len(hexa)
        try:
            if hexa_len == 3:
                c = int(hexa[1:], base=16)
                rgb = (c, c, c)
            elif hexa_len == 7:
                rgb = (
                    int(hexa[1:3], base=16),
                    int(hexa[3:5], base=16),
                    int(hexa[5:7], base=16),
                )
        except ValueError:
            raise ColorError(
                f"The hexa `{hexa}` of color can't to be parsing."
            ) from None
        else:
            return rgb

    @staticmethod
    def truecolor_to_256(rgb: Tuple) -> int:

        greyscale = (rgb[0] // 11, rgb[1] // 11, rgb[2] // 11)
        if greyscale[0] == greyscale[1] == greyscale[2]:
            return 232 + greyscale[0]
        else:
            return (
                round(rgb[0] / 51) * 36
                + round(rgb[1] / 51) * 6
                + round(rgb[2] / 51)
                + 16
            )

    @classmethod
    def escape_color(
        cls,
        hexa: Optional[str] = None,
        r: int = 0,
        g: int = 0,
        b: int = 0,
        depth: ColorDepthType = "fg",
    ) -> str:
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
        rgb = cls.generate_rgb(hexa) if hexa else (r, g, b)

        if not Color.TRUE_COLOR:
            return "\033[{};5;{}m".format(dint, Color.truecolor_to_256(rgb=rgb))

        return "\033[{};2;{};{};{}m".format(dint, *rgb)

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
    def by_name(cls, name: str, depth: ColorDepthType = "fg"):
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

    @staticmethod
    def is_color(code: Union[str, List, Tuple]) -> bool:
        """Return True if code is color else False.
        Like: '#FF0000', '#FF', 'red', [255, 0, 0], (0, 255, 0)
        """

        if type(code) == str:
            return (
                _COLOR_RE.match(str(code)) is not None
                or COLOR_CODE.get(code) is not None
            )
        elif isinstance(code, list) or isinstance(code, tuple):
            if len(code) != 3:
                return False
            for c in code:
                if not (0 <= c <= 255):
                    return False
            else:
                return True
        else:
            return False


class Style(object):
    def __init__(
        self,
        *,
        color: Optional[str] = None,
        bg_color: Optional[str] = None,
        bold: Optional[bool] = None,
        dark: Optional[bool] = None,
        italic: Optional[bool] = None,
        underline: Optional[bool] = None,
        blink: Optional[bool] = None,
        strick: Optional[bool] = None,
    ) -> None:
        self.color = color if Color.is_color(color) else None
        self.bg_color = bg_color if Color.is_color(bg_color) else None

        self._set_attributes = sum(
            (
                bold is not None and 1,
                dark is not None and 2,
                italic is not None and 4,
                underline is not None and 8,
                blink is not None and 16,
                strick is not None and 32,
            )
        )
        self._attributes = sum(
            (
                bold and 1 or 0,
                dark and 2 or 0,
                italic and 4 or 0,
                underline and 8 or 0,
                blink and 16 or 0,
                strick and 32 or 0,
            )
        )

        self._style_definition: Optional[str] = None
        self._ansi: Optional[str] = None
        self._null = not (self._set_attributes or color or bg_color)

    def __str__(self) -> str:
        if self._style_definition is None:
            style_res: List[str] = []
            append = style_res.append

            bits = self._set_attributes
            bits2 = self._attributes
            if bits & 0b000001111:
                if bits & 1:
                    append("bold" if bits2 & 1 else "not bold")
                if bits & (1 << 1):
                    append("dark" if bits2 & (1 << 1) else "not dark")
                if bits & (1 << 2):
                    append("italic" if bits2 & (1 << 2) else "not italic")
                if bits & (1 << 3):
                    append("underline" if bits2 & (1 << 3) else "not underline")
            if bits & 0b111110000:
                if bits & (1 << 4):
                    append("blink" if bits2 & (1 << 4) else "not blink")
                if bits & (1 << 5):
                    append("strick" if bits2 & (1 << 5) else "not strick")

            if self.color:
                style_res.append(self.color)
            if self.bg_color:
                style_res.extend(("on", self.bg_color))

            self._style_definition = " ".join(style_res) or "none"

        return self._style_definition

    def _make_ansi_code(self) -> str:
        if self._ansi is None:
            sgr: List[str] = []
            fx_map = Fx.code_map

            if attributes := self._set_attributes & self._attributes:
                sgr.extend(fx_map[bit] for bit in range(6) if attributes & (1 << bit))

            self._ansi = f"{Fx.start}{';'.join(sgr)}{Fx.end}"
            if self.color:
                self._ansi += (
                    Color.by_name(self.color)
                    if not self.color.startswith("#")
                    else Color.fg(self.color)
                )
            if self.bg_color:
                self._ansi += (
                    Color.by_name(self.bg_color, depth="bg")
                    if not self.bg_color.startswith("#")
                    else Color.bg(self.bg_color)
                )

        # print(repr(self._ansi))
        return self._ansi

    def render(self, text: str) -> str:
        attrs = self._make_ansi_code()
        return f"{attrs}{text}{Fx.reset}" if attrs else text

    def test(self, text: Optional[str] = None):
        text = text or str(self)
        print(self.render(text))

    def __add__(self, style: Optional["Style"]) -> "Style":
        if not (isinstance(style, Style) or Style is None):
            return NotImplemented

        if style is None or style._null:
            return self

        new_style: Style = self.__new__(Style)
        new_style._ansi = None
        new_style._style_definition = None
        new_style.color = style.color or self.color
        new_style.bg_color = style.bg_color or self.bg_color
        new_style._attributes = (self._attributes & ~style._set_attributes) | (
            style._attributes & style._set_attributes
        )
        new_style._set_attributes = self._set_attributes | style._set_attributes
        new_style._null = style._null or self._null

        return new_style

    @classmethod
    def parse(cls, style_definition: str) -> "Style":
        FX_ATTRIBUTES = Fx.supports
        color = ""
        bg_color = ""
        attributes = {}

        words = iter(style_definition.split())
        for original_word in words:
            word = original_word.lower()

            if word == "on":
                word = next(words, "")
                if not word:
                    raise StyleSyntaxError("color expected after 'on'")
                if Color.is_color(word):
                    bg_color = word
                else:
                    raise StyleSyntaxError(
                        f"unable to parse {word!r} as background color."
                    )

            elif word in FX_ATTRIBUTES:
                attributes[FX_ATTRIBUTES[word]] = True

            elif Color.is_color(word):
                color = word
            else:
                raise StyleSyntaxError(f"unable to parse {word!r} as color.")

        return Style(color=color, bg_color=bg_color, **attributes)

    @staticmethod
    def render_style(_msg: str, /, *, _style_sub=_STYLE_RE.sub):
        def do_replace(match: Match[str]) -> str:
            raw, fx_tag, content, color_code, bg_color_code = match.groups()
            # print(raw, fx_tag, content, color_code, bg_color_code)

            if not color_code and not fx_tag and not bg_color_code:
                return raw

            try:
                if fx_tag is None:
                    # No fx then get empty.
                    font_style = ""
                elif fx_tag.startswith("(") and fx_tag.endswith(")"):
                    # Has multi fx tags.
                    fx_tag = fx_tag[1:-1]
                    font_style = "".join(
                        Fx.by_name(fx_code.strip()) for fx_code in fx_tag.split(",")
                    )
                else:
                    # Only one.
                    font_style = Fx.by_name(fx_tag)

                # Get color hexa.
                if color_code and color_code.startswith("#"):
                    color_style = Color.fg(color_code)
                else:
                    color_style = Color.by_name(color_code, depth="fg")

                if bg_color_code and bg_color_code.startswith("#"):
                    bg_color_style = Color.bg(bg_color_code)
                else:
                    bg_color_style = Color.by_name(bg_color_code, depth="bg")

                return f"{font_style}{color_style}{bg_color_style}{content}\033[0m"
            except KeyError:
                return raw

        return _style_sub(do_replace, _msg)

    @classmethod
    def remove_style(cls, _msg: str, /, *, _style_sub=_STYLE_RE.sub):
        def do_replace(match: Match[str]) -> str:
            raw, fx, content, color_code, color_bg_code = match.groups()

            if not color_code and not fx and not color_bg_code:
                return raw

            return content

        return _style_sub(do_replace, _msg)

    @classmethod
    def clear_text(cls, _msg: str) -> str:
        return Fx.pure(cls.remove_style(_msg))

    @classmethod
    def null(cls) -> "Style":
        return NULL_STYLE


NULL_STYLE = Style()


if __name__ == "__main__":
    import doctest

    doctest.testmod(verbose=True)
