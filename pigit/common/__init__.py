# -*- coding:utf-8 -*-
import os

# For windows print color.
if os.name == "nt":
    os.system("")

from .emoji import Emoji
from .style import *
from .utils import *
from .str_utils import *


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
