# -*- coding:utf-8 -*-
import os

# For windows print color.
if os.name == "nt":
    os.system("")

from .emotion import Emotion
from .style import Color, BoxSymbol
from .escape import Fx, Cursor
from .utils import run_cmd, exec_cmd, confirm, color_print, is_color, similar_command
from .str_utils import get_width, shorten, adjudgment_type, get_file_icon


# yapf: disable
__all__ = [
    "Emotion", "Color", "BoxSymbol", "Fx", "Cursor",
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
