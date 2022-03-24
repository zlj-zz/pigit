from typing import Any, Iterable, List, Optional, Union
import sys, platform
from itertools import islice
from inspect import isclass
from shutil import get_terminal_size

from .style import Style
from .markup import render_markup
from .segment import Segment
from .emoji import Emoji
from .errors import NotRenderableError, StyleSyntaxError, MissingStyle


class Console:
    def __init__(self) -> None:
        self._buffer = []
        self._size = None

    @property
    def size(self):
        if not self._size:
            self._size = get_terminal_size()

        return self._size

    @property
    def width(self):
        return self.size.columns

    @property
    def hight(self):
        return self.size.lines

    @property
    def system(self) -> str:
        """Return the OS name.

        Values: 'Linux', 'Darwin', 'Java', 'Window', ''
        """

        return platform.system()

    @property
    def encoding(self):
        return sys.getdefaultencoding().lower()

    def get_style(
        self, name: Union[str, Style], *, default: Optional[Union[str, Style]] = None
    ) -> Style:
        if isinstance(name, Style):
            return name

        try:
            return Style.parse(name)
        except StyleSyntaxError as e:
            if default is not None:
                return self.get_style(default)
            raise MissingStyle(f"Failed to get style {name!r}; {e}") from None

    def render_lines(
        self,
        renderable,
        max_width,
        *,
        style: Optional[Style] = None,
        pad: bool = True,
        new_lines: bool = False,
    ) -> List[Segment]:
        _rendered = render_markup(renderable)
        if style:
            _rendered = Segment.apply_style(_rendered, style)
        lines = list(
            islice(Segment.split_and_crop_lines(_rendered, max_width), None, None)
        )
        return lines

    @classmethod
    def render_str(
        cls, text: str, /, *, allow_style: bool = True, allow_emoji: bool = True
    ) -> str:
        """Render color, font and emoji code in string.

        Args:
            text (str): The text string that need be rendered.
            allow_style (bool, optional): whether render color and font. Defaults to True.
            allow_emoji (bool, optional): whether render emoji. Defaults to True.

        Returns:
            str: the rendered text string.
        """

        if allow_emoji:
            text = Emoji.render_emoji(text)

        if allow_style:
            text = Style.render_style(text)

        return text

    def render_str2(self, text: str, /, *, style: Optional[str] = None):
        return Segment(text, style)

    def render(self, obj: Any):
        render_iterable: Iterable
        if isinstance(obj, str):
            render_iterable = [self.render_str(obj)]
        elif hasattr(obj, "__render__") and not isclass(obj):
            render_iterable = obj.__render__(self)
        else:
            raise NotRenderableError(
                f"{obj!r} can't render without `__render__` method."
            )

        try:
            render_iter = iter(render_iterable)
        except TypeError:
            raise NotRenderableError(
                f"object {render_iterable!r} is not renderable"
            ) from None

        for render_output in render_iter:
            if isinstance(render_output, str):
                yield render_output
            else:
                yield from self.render(render_output)

    def echo(self, *values, sep: str = " ", end: str = "\n", flush: bool = True):
        for value in values:
            render_iter = self.render(value)
            self._buffer.append("".join(render_iter))

        # print(self._buffer, len(self._buffer))

        if self._buffer:
            print(*self._buffer, sep=sep, end=end, flush=flush)
            del self._buffer[:]
