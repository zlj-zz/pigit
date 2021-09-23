# -*- coding:utf-8 -*-
import os

# For windows print color.
if os.name == "nt":
    os.system("")

from .emotion import Emotion
from .style import Color, Symbol
from .escape import Fx, Cursor

__all__ = ["Emotion", "Color", "Symbol", "Fx", "Cursor"]


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
