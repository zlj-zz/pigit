# -*- coding:utf-8 -*-

"""This file support some str util method.

Docs Test

    The width occupied by a given character when displayed.

        >>> get_width(ord('a'))
        1
        >>> get_width(ord('中'))
        2
        >>> get_width(ord('Ç'))
        1

    Intercepts a string by a given length.

        >>> shorten('Hello world!', 9, placeholder='^-^')
        'Hello ^-^'
        >>> shorten('Hello world!', 9, placeholder='^-^', front=True)
        '^-^world!'

    Chop cell.
        >>> chop_cells('12345678', 4)
        ['1234', '5678']
        >>> chop_cells('12345678', 10)
        ['12345678']

    Set cell size
        >>> set_cell_size('123456', 4)
        '1234'
        >>> set_cell_size('123456', 6)
        '123456'
        >>> set_cell_size('123456', 8)
        '123456  '
"""

from typing import List, Tuple
from functools import lru_cache


WIDTHS: List[Tuple[int, int]] = [
    (126, 1),
    (159, 0),
    (687, 1),
    (710, 0),
    (711, 1),
    (727, 0),
    (733, 1),
    (879, 0),
    (1154, 1),
    (1161, 0),
    (4347, 1),
    (4447, 2),
    (7467, 1),
    (7521, 0),
    (8369, 1),
    (8426, 0),
    (9000, 1),
    (9002, 2),
    (11021, 1),
    (12350, 2),
    (12351, 1),
    (12438, 2),
    (12442, 0),
    (19893, 2),
    (19967, 1),
    (55203, 2),
    (63743, 1),
    (64106, 2),
    (65039, 1),
    (65059, 0),
    (65131, 2),
    (65279, 1),
    (65376, 2),
    (65500, 1),
    (65510, 2),
    (120831, 1),
    (262141, 2),
    (1114109, 1),
]


@lru_cache(maxsize=1024)
def get_width(r: int) -> int:
    """Gets the width occupied by characters on the command line."""

    if r in {0xE, 0xF}:
        return 0
    return next((wid for num, wid in WIDTHS if r <= num), 1)


def get_char_width(character: str) -> int:
    return get_width(ord(character))


def cell_len(cell: str) -> int:
    return sum(get_char_width(ch) for ch in cell)


# TODO: This is inefficient
# TODO: This might not work with CWJ type characters
def chop_cells(text: str, max_size: int, position: int = 0) -> List[str]:
    """Break text in to equal (cell) length strings."""
    _get_character_cell_size = get_char_width
    characters = [
        (character, _get_character_cell_size(character)) for character in text
    ][::-1]
    total_size = position
    lines: List[List[str]] = [[]]
    append = lines[-1].append

    pop = characters.pop
    while characters:
        character, size = pop()
        if total_size + size > max_size:
            lines.append([character])
            append = lines[-1].append
            total_size = size
        else:
            total_size += size
            append(character)
    return ["".join(line) for line in lines]


def set_cell_size(text: str, total: int) -> str:
    """Set the length of a string to fit within given number of cells."""

    cell_size = cell_len(text)
    if cell_size == total:
        return text
    if cell_size < total:
        return text + " " * (total - cell_size)

    start = 0
    end = len(text)

    # Binary search until we find the right size
    while True:
        pos = (start + end) // 2
        before = text[: pos + 1]
        before_len = cell_len(before)
        if before_len == total + 1 and cell_len(before[-1]) == 2:
            return f"{before[:-1]} "
        if before_len == total:
            return before
        if before_len > total:
            end = pos
        else:
            start = pos


def wrap_color_str(line: str, width: int):
    """Warp a colored line.
    Wrap a colored string according to the width of the restriction.
    Args:
        line: A colored string.
        width: Limit width.
    """
    # line = re.sub(r"\x1b(?P<need>\[\d+;*\d*[suABCDf])", "\g<need>", line)
    # line = line.replace("\\", "\\\\")
    line_len = len(line)
    lines = []
    start = 0
    i = 0
    count = 0
    while i < line_len:
        if line[i] == "\x1b":
            while line[i] not in ["m"]:
                i += 1
        i += 1
        count += get_char_width(line[i]) if i < line_len else 0
        if count + 1 >= width - 1:
            i += 1
            lines.append(line[start:i])
            start = i
            count = 0
    if start < line_len:
        lines.append(line[start:])

    return lines


def shorten(
    text: str, width: int, placeholder: str = "...", front: bool = False
) -> str:
    """Truncate exceeded characters.

    Args:
        text (str): Target string.
        width (int): Limit length.
        placeholder (str): Placeholder string. Defaults to "..."
        front (bool): Head hidden or tail hidden. Defaults to False.

    Returns:
        (str): shorten string.
    """

    if len(text) > width:
        if front:
            text = placeholder + text[-width + len(placeholder) :]
        else:
            text = text[: width - len(placeholder)] + placeholder

    return text


def byte_str2str(text: str) -> str:
    temp = f"b'{text}'"
    # use ~eval transfrom `str` to `bytes`
    b = eval(temp)
    return str(b, encoding="utf-8")


if __name__ == "__main__":
    import doctest

    doctest.testmod(verbose=True)

    for line in chop_cells("""窗前明月光，疑似地上霜。举头望明月，低头是故乡。 静夜思  """, 12):
        print(line)
