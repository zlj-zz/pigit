from typing import Any, Iterable, Optional
from inspect import isclass
from shutil import get_terminal_size

from pigit.render.segment import Segment


from .style import Style
from .emoji import Emoji
from .errors import NotRenderableError


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

    def _collect(self, objs):
        pass

    def render_str(
        self, text: str, /, *, allow_style: bool = True, allow_emoji: bool = True
    ) -> str:
        """Render color, font and emoji code in string.

        Args:
            text (str): The text string that need be rendered.
            hightlight (bool, optional): whether render color and font. Defaults to True.
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
            raise NotRenderableError(f"object {render_iterable!r} is not renderable")

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
