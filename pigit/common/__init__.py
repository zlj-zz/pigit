# -*- coding:utf-8 -*-
import os

# For windows print color.
if os.name == "nt":
    os.system("")

from .emoji import Emoji
from .style import Fx, Color, BoxSymbol, render_style, is_color
from .utils import run_cmd, exec_cmd, confirm, similar_command, get_current_shell
from .str_utils import get_width, shorten, adjudgment_type, get_file_icon


# yapf: disable
__all__ = [
    "Emoji", "Color", "BoxSymbol", "Fx", "render_style", "is_color",
    "run_cmd", "exec_cmd", "confirm", "similar_command", "get_current_shell",
    "get_width", "shorten", "adjudgment_type", "get_file_icon",
]
# yapf: enable


def render_str(
    text: str, /, *, hightlight: bool = True, allow_emoji: bool = True
) -> str:
    """Render color, font and emoji code in string.

    Args:
        text (str): The text string that need be rendered.
        hightlight (bool, optional): whether render color and font. Defaults to True.
        allow_emoji (bool, optional): whether render emoji. Defaults to True.

    Returns:
        str: the rendered text string.
    """

    if hightlight:
        text = render_style(text)

    if allow_emoji:
        text = Emoji.render(text)

    return text
