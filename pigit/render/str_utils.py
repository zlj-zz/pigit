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


def garbled_code_analysis(v: str):
    # TODO: not best way.
    temp = f"b'{v}'"
    temp = eval(temp)
    return str(temp, encoding="utf-8")


if __name__ == "__main__":
    import doctest

    doctest.testmod(verbose=True)
