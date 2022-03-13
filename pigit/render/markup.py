from typing import List, Union

from .emoji import Emoji
from .style import _STYLE_RE, Style
from .segment import Segment


def _parse(markup: str):
    position = 0

    for match in _STYLE_RE.finditer(markup):
        full_text, fx, pure_text, color, bg_color = match.groups()
        start, end = match.span()
        if start > position:
            yield markup[position:start], None, None, None
        if fx or color or bg_color:
            yield pure_text, fx, color, bg_color
            position = end

    if position < len(markup):
        yield markup[position:], None, None, None


def render_markup(markup: str, style: Union[str, Style] = "", emoji: bool = True):
    if emoji:
        markup = Emoji.render_emoji(markup)

    renderables: List[Segment] = []
    for text, fx, color, bg_color in _parse(markup):
        sgr = []
        if fx:
            sgr.append(fx)
        if color:
            sgr.append(color)
        if bg_color:
            sgr.extend(("on", bg_color))

        renderables.append(Segment(text, style=Style.parse(" ".join(sgr))))

    return renderables
