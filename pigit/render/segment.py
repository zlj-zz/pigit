from typing import TYPE_CHECKING, Iterable, List, Optional

from .str_utils import cell_len, set_cell_size, chop_cells
from .style import Style, Fx


if TYPE_CHECKING:
    from .console import Console


class Segment:
    def __init__(self, text: str = "", style: Optional[Style] = None) -> None:
        self.text = text
        self.style = style
        self._length = len(text)

    def __render__(self, console: "Console"):
        if self.style:
            yield self.style.render(self.text)
        else:
            yield self.text

    def __len__(self):
        return self._length

    def __bool__(self):
        return bool(self._length)

    def __repr__(self) -> str:
        return f"<Segment {self.text!r} style='{str(self.style)}' >"

    @property
    def cell_len(self):
        return cell_len(Fx.pure(self.text))

    @property
    def cell_len_without_tag(self):
        return cell_len(Style.clear_text(self.text))

    @classmethod
    def line(cls) -> "Segment":
        """Make a new line segment."""
        return cls("\n")

    @classmethod
    def split_and_crop_lines(
        cls,
        segments: Iterable["Segment"],
        length: int,
        style: Optional[str] = None,
        pad: bool = True,
        include_new_lines: bool = False,
    ) -> Iterable[List["Segment"]]:
        """Split segments in to lines, and crop lines greater than a given length.

        Args:
            segments (Iterable[Segment]): An iterable of segments, probably
                generated from console.render.
            length (int): Desired line length.
            style (Style, optional): Style to use for any padding.
            pad (bool): Enable padding of lines that are less than `length`.

        Returns:
            Iterable[List[Segment]]: An iterable of lines of segments.
        """
        line: List[Segment] = []
        append = line.append

        adjust_line_length = cls.adjust_line_length
        new_line_segment = cls("\n")

        for segment in segments:
            if "\n" in segment.text:
                text = segment.text
                style = segment.style
                while text:
                    _text, new_line, text = text.partition("\n")
                    if _text:
                        append(cls(_text, style))
                    if new_line:
                        cropped_line = adjust_line_length(
                            line, length, style=style, pad=pad
                        )
                        if include_new_lines:
                            cropped_line.append(new_line_segment)
                        yield cropped_line
                        del line[:]
            else:
                append(segment)
        if line:
            yield adjust_line_length(line, length, style=style, pad=pad)

    @classmethod
    def adjust_line_length(
        cls,
        line: List["Segment"],
        length: int,
        style: Optional[str] = None,
        pad: bool = True,
    ) -> List["Segment"]:
        """Adjust a line to a given width (cropping or padding as required).

        Args:
            segments (Iterable[Segment]): A list of segments in a single line.
            length (int): The desired width of the line.
            style (Style, optional): The style of padding if used (space on the end). Defaults to None.
            pad (bool, optional): Pad lines with spaces if they are shorter than `length`. Defaults to True.

        Returns:
            List[Segment]: A line of segments with the desired length.
        """
        line_length = sum(segment.cell_len for segment in line)
        new_line: List[Segment]

        if line_length < length:
            if pad:
                new_line = line + [cls(" " * (length - line_length), style)]
            else:
                new_line = line[:]
        elif line_length > length:
            new_line = []
            append = new_line.append
            line_length = 0
            for segment in line:
                segment_length = segment.cell_len
                if line_length + segment_length < length:
                    append(segment)
                    line_length += segment_length
                else:
                    text = segment.text
                    text = set_cell_size(text, length - line_length)
                    append(cls(text, segment.style))
                    break
        else:
            new_line = line[:]
        return new_line

    @classmethod
    def apply_style(cls, segments: Iterable["Segment"], style: Optional[Style] = None):
        result_segments = segments
        if style:
            apply = style.__add__
            result_segments = (
                cls(segment.text, apply(segment.style)) for segment in result_segments
            )
        return result_segments
