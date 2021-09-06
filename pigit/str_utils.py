# -*- coding:utf-8 -*-

"""This file support some str util method."""

# yapf: disable
widths:list[tuple] = [
    (126, 1), (159, 0), (687, 1), (710, 0), (711, 1), (727, 0), (733, 1), (879, 0),
    (1154, 1), (1161, 0), (4347, 1), (4447, 2), (7467, 1),
    (7521, 0), (8369, 1), (8426, 0), (9000, 1), (9002, 2),
    (11021, 1), (12350, 2), (12351, 1), (12438, 2), (12442, 0), (19893, 2),
    (19967, 1), (55203, 2), (63743, 1), (64106, 2), (65039, 1), (65059, 0),
    (65131, 2), (65279, 1), (65376, 2), (65500, 1), (65510, 2), (120831, 1),
    (262141, 2), (1114109, 1),
]
# yapf: enable


def get_width(r: int) -> int:
    """Gets the width occupied by characters on the command line.

    >>> get_width(ord('a'))
    1
    >>> get_width(ord('中'))
    2
    >>> get_width(ord('Ç'))
    1
    """
    global widths
    if r == 0xE or r == 0xF:
        return 0
    for num, wid in widths:
        if r <= num:
            return wid
    return 1


File_Icons: dict[str, str] = {
    "": "",
    "Batch": "",
    "C": "",
    "C#": "",
    "C++": "",
    "CSS": "",
    "Dart": "",
    "Groovy": "",
    "Go": "",
    "HTML": "",
    "Java": "",
    "Java Scirpt": "",
    "Lua": "",
    "Kotlin": "",
    "Markdown": "",
    "PHP": "",
    "Propertie": "",
    "Python": "",
    "R": "ﳒ",
    "React": "",
    "Ruby": "",
    "Rust": "",
    "ROS Message": "",
    "reStructuredText": "",
    "Shell": "",
    "Swift": "",
    "SQL": "",
    "Type Scirpt": "",
    "Vim Scirpt": "",
    "Vue": "﵂",
    "YAML": "",
    "XML": "",
}


def get_file_icon(file_type: str) -> str:
    """According file type return icon.

    Args:
        file_type (str): type string.

    Returns:
        str: icon.

    >>> get_file_icon('Python')
    ''
    >>> get_file_icon('Lua')
    ''
    >>> get_file_icon('xxxxxxxxxx')
    ''
    """
    #     
    return File_Icons.get(file_type, "")


def shorten(
    text: str, width: int, placeholder: str = "...", front: bool = False
) -> str:
    # type:(str, int, str, bool) -> str
    """Truncate exceeded characters.

    Args:
        text (str): Target string.
        width (int): Limit length.
        placeholder (str): Placeholder string. Defaults to "..."
        front (bool): Head hidden or tail hidden. Defaults to False.

    Returns:
        (str): shorten string.

    >>> shorten('Hello world!', 9, placeholder='^-^')
    'Hello ^-^'
    >>> shorten('Hello world!', 9, placeholder='^-^', front=True)
    '^-^world!'
    """

    if len(text) > width:
        if front:
            text = placeholder + text[-width + len(placeholder) :]
        else:
            text = text[: width - len(placeholder)] + placeholder

    return text


if __name__ == "__main__":
    import doctest

    doctest.testmod()
