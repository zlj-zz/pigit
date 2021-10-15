# -*- coding:utf-8 -*-
import os

# For windows print color.
if os.name == "nt":
    os.system("")

from .emoji import Emoji
from .style import Fx, Color, BoxSymbol, render_style
from .console import Cursor, Term
from .utils import run_cmd, exec_cmd, confirm, color_print, is_color, similar_command
from .str_utils import get_width, shorten, adjudgment_type, get_file_icon


# yapf: disable
__all__ = [
    "Emoji", "Color", "BoxSymbol", "Fx", "Cursor", "Term",
    "run_cmd", "exec_cmd", "confirm", "color_print", "is_color", "similar_command",
    "get_width", "shorten", "adjudgment_type", "get_file_icon",
]
# yapf: enable


class TermColor:
    """Terminal print color class."""

    Red = Color.fg("#FF6347")  # Tomato
    Green = Color.fg("#98FB98")  # PaleGreen
    DeepGreen = Color.fg("#A4BE8C")  # PaleGreen
    Yellow = Color.fg("#EBCB8C")
    Gold = Color.fg("#FFD700")  # Gold
    SkyBlue = Color.fg("#87CEFA")
    MediumVioletRed = Color.fg("#C71585")
    Symbol = {"+": Color.fg("#98FB98"), "-": Color.fg("#FF6347")}


def render_str(
    _msg: str, /, *, hightlight: bool = True, allow_emoji: bool = True
) -> str:
    if hightlight:
        _msg = render_style(_msg)

    if allow_emoji:
        _msg = Emoji.render(_msg)

    return _msg
