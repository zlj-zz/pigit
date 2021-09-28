# -*- coding:utf-8 -*-

"""This file support some str util method."""

# yapf: disable
WIDTHS:list[tuple[int,int]] = [
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
    global WIDTHS
    if r == 0xE or r == 0xF:
        return 0
    for num, wid in WIDTHS:
        if r <= num:
            return wid
    return 1


# Mark the type corresponding to the file suffix.
# abcdefg hijklmn opq rst uvw xyz
SUFFIX_TYPE: dict[str, str] = {
    "": "",
    "bat": "Batch",
    "c": "C",
    "cfg": "Properties",
    "conf": "Properties",
    "cpp": "C++",
    "cs": "C#",
    "css": "CSS",
    "dart": "Dart",
    "dea": "XML",
    "go": "Go",
    "gradle": "Groovy",
    "h": "C",
    "hpp": "C++",
    "htm": "HTML",
    "html": "HTML",
    "java": "Java",
    "js": "Java Script",
    "json": "Json",
    "jsx": "React",
    "kt": "Kotlin",
    "launch": "XML",
    "less": "CSS",
    "lua": "Lua",
    "markdown": "Markdown",
    "md": "Markdown",
    "msg": "ROS Message",
    "php": "PHP",
    "plist": "XML",
    "properties": "Propertie",
    "py": "Python",
    "r": "R",
    "rb": "Ruby",
    "rc": "Properties",
    "rs": "Rust",
    "rst": "reStructuredText",
    "rviz": "YAML",
    "ts": "Type Script",
    "tsx": "React",
    "sass": "CSS",
    "scss": "CSS",
    "sh": "Shell",
    "sql": "SQL",
    "srdf": "YAML",
    "srv": "ROS Message",
    "swift": "Swift",
    "toml": "Properties",
    "urdf": "XML",
    "vim": "Vim Scirpt",
    "vue": "Vue",
    "xhtml": "HTML",
    "xml": "XML",
    "yaml": "YAML",
    "yml": "YAML",
    "zsh": "Shell",
}

# Mark the type of some special files.
SPECIAL_NAMES: dict[str, str] = {
    "license": "LICENSE",
    "requirements.txt": "Pip requirement",
    "vimrc": "Vim Scirpt",
}


def adjudgment_type(file: str, original: bool = False) -> str:
    """Get file type.

    First, judge whether the file name is special, and then query the
    file suffix. Otherwise, the suffix or name will be returned as is.

    Args:
        file (str): file name string.
        original (bool, option): whether return origin when match failed.

    Returns:
        (str): file type.

    >>> adjudgment_type('test.py')
    'Python'
    >>> adjudgment_type('xxxxx')
    'unknown'
    >>> adjudgment_type('xxxxx', True)
    'xxxxx'
    """

    pre_type = SPECIAL_NAMES.get(file.lower(), None)
    if pre_type:
        return pre_type

    suffix = file.split(".")[-1]
    suffix_type = SUFFIX_TYPE.get(suffix.lower(), None)
    if suffix_type:
        return suffix_type
    else:
        return suffix if original else "unknown"


FILE_ICONS: dict[str, str] = {
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
    "snippets": "",
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
    return FILE_ICONS.get(file_type, "")


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
