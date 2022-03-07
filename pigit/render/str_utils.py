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

    Garbled code analysis.

        # >>> garbled_code_analysis("\\346\\265\\213\\350\\257\\225\\344\\270\\255\\346\\226\\207\\345\\220\\215\\347\\247\\260")
        中文测试名称
"""

# from typing import Final # python3.8

WIDTHS: list[tuple[int, int]] = [
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


def get_width(r: int) -> int:
    """Gets the width occupied by characters on the command line."""

    if r == 0xE or r == 0xF:
        return 0
    for num, wid in WIDTHS:
        if r <= num:
            return wid
    return 1


def get_char_width(character: str) -> int:
    return get_width(ord(character))


def cell_len(cell: str) -> int:
    return sum(get_char_width(ch) for ch in cell)


# TODO: This is inefficient
# TODO: This might not work with CWJ type characters
def chop_cells(text: str, max_size: int, position: int = 0) -> list[str]:
    """Break text in to equal (cell) length strings."""
    _get_character_cell_size = get_char_width
    characters = [
        (character, _get_character_cell_size(character)) for character in text
    ][::-1]
    total_size = position
    lines: list[list[str]] = [[]]
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
            return before[:-1] + " "
        if before_len == total:
            return before
        if before_len > total:
            end = pos
        else:
            start = pos


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


# TODO: not best way.
def garbled_code_analysis(v: str):
    temp = f"b'{v}'"
    temp = eval(temp)
    return str(temp, encoding="utf-8")


if __name__ == "__main__":
    import doctest

    doctest.testmod(verbose=True)

    for line in chop_cells("""窗前明月光，疑似地上霜。举头望明月，低头是故乡。 静夜思  """, 12):
        print(line)
