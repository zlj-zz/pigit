# -*- coding:utf-8 -*-

import sys
from collections import Counter
from math import sqrt
from typing import Iterable, Tuple, Dict


def strtobool(s: str) -> bool:
    """Convert a string representation of truth to true (1) or false (0).

    Raises:
        ValueError: if val is anything else.

    Returns:
        bool

    Docs Test:
        >>> strtobool('y')
        True
        >>> strtobool('Y')
        True
        >>> strtobool('n')
        False
        >>> strtobool('N')
        False
    """
    s = s.lower()

    if s in {"y", "yes", 't', 'true', "on", "1"}:
        return True
    elif s in {"n", "no", "f", "false", "off", "0"}:
        return False
    else:
        raise ValueError('Not support string.')


def traceback_info(extra_msg: str = "null") -> str:
    """Get traceback information.

    Args:
        extra_msg (str, optional): extra custom message. Defaults to "null".

    Returns:
        str: formatted traceback information.
    """
    exc_type, exc_value, exc_obj = sys.exc_info()
    if exc_type is None or exc_value is None or exc_obj is None:
        return ""

    err_value = exc_type.__name__
    lineno = exc_obj.tb_lineno
    filename = exc_obj.tb_frame.f_code.co_filename

    return (
        f"File {filename}, line {lineno}, {err_value}:{exc_value}, remark:[{extra_msg}]"
    )


def confirm(text: str = "", default: bool = True) -> bool:
    """Obtain confirmation results.
    Args:
        text (str): Confirmation prompt.
        default (bool): Result returned when unexpected input.

    Returns:
        (bool): Confirm result.
    """
    input_command: str = input(text).strip().lower()

    if input_command in {"n", "no", "N", "No"}:
        return False
    elif input_command in {"y", "yes", "Y", "Yes"}:
        return True
    else:
        return default


def similar_command(command: str, all_commands: Iterable) -> str:
    """Get the most similar command with K-NearestNeighbor.

    Args:
        command (str): command string.
        all_commands (list): The list of all command.

    Returns:
        (str): most similar command string.

    Docs test
        >>> commands = [
        ...     'branch', 'working tree', 'index', 'log', 'push',
        ...     'pull', 'tag','commit','conflict'
        ... ]
        >>> similar_command('br', commands)
        'branch'
        >>> similar_command('wo', commands)
        'working tree'
        >>> similar_command('com', commands)
        'commit'
    """
    #  The dictionary of letter frequency of all commands.
    words: dict = {word: dict(Counter(word)) for word in all_commands}
    # Letter frequency of command.
    fre = dict(Counter(command))
    # The distance between the frequency of each letter in the command
    # to be tested and all candidate commands, that is the difference
    # between the frequency of letters.
    frequency_difference: dict[str, list[int]] = {
        word: [fre[ch] - words[word].get(ch, 0) for ch in command]
        + [words[word][ch] - fre.get(ch, 0) for ch in word]
        for word in words
    }
    # Square of sum of squares of word frequency difference.
    frequency_sum_square: list[Tuple[str, int]] = list(
        map(
            lambda item: (item[0], int(sqrt(sum(map(lambda i: i**2, item[1]))))),
            frequency_difference.items(),
        )
    )

    # The value of `frequency_sum_square` is multiplied by the weight to find
    # the minimum.
    # Distance weight: compensate for the effect of length difference.
    # Compare Weight: The more similar the beginning, the higher the weight.
    # sourcery skip: inline-immediately-returned-variable, or-if-exp-identity
    min_frequency_command: str = min(
        frequency_sum_square,
        key=lambda item: item[1]
        * (
            len(command) / len(item[0])
            if len(command) / len(item[0])
            else len(item[0]) / len(command)
        )
        # Returns how many identical letters are compared from the head. sigmod to 0 ~ 1.
        * (1 / (len(list(filter(lambda i: i[0] == i[1], zip(command, item[0])))) + 1)),
    )[0]
    return min_frequency_command


# Mark the type corresponding to the file suffix.
# abcdefg hijklmn opq rst uvw xyz
SUFFIX_TYPE: Dict[str, str] = {
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
    "ini": "Ini",
    "java": "Java",
    "js": "Java Script",
    "json": "Json",
    "jsx": "React",
    "kt": "Kotlin",
    "launch": "XML",
    "less": "CSS",
    "lua": "Lua",
    "log": "Log",
    "m": "Object-C",
    "mm": "Object-C++",
    "markdown": "Markdown",
    "md": "Markdown",
    "msg": "ROS Message",
    "php": "PHP",
    "plist": "XML",
    "properties": "Properties",
    "py": "Python",
    "r": "R",
    "rb": "Ruby",
    "rc": "Properties",
    "rs": "Rust",
    "rst": "reStructuredText",
    "ts": "Type Script",
    "tsx": "React",
    "sass": "CSS",
    "scss": "CSS",
    "sh": "Shell",
    "sql": "SQL",
    "srv": "ROS Message",
    "swift": "Swift",
    "toml": "Properties",
    "vb": "Visual Basic",
    "vim": "Vim Script",
    "vue": "Vue",
    "xhtml": "HTML",
    "xml": "XML",
    "yaml": "YAML",
    "yml": "YAML",
    "zsh": "Shell",
}

# Mark the type of some special files.
SPECIAL_NAMES: Dict[str, str] = {
    "license": "LICENSE",
    "requirements.txt": "Pip requirement",
    "vimrc": "Vim Script",
    "dockerfile": "Docker",
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

    Docs test
        >>> adjudgment_type('py')
        'Python'
        >>> adjudgment_type('xx')
        'unknown'
        >>> adjudgment_type('xx', True)
        'xx'
    """
    if pre_type := SPECIAL_NAMES.get(file.lower()):
        return pre_type

    suffix = file.split(".")[-1]
    if suffix_type := SUFFIX_TYPE.get(suffix.lower()):
        return suffix_type
    else:
        return suffix if original else "unknown"


FILE_ICONS: Dict[str, str] = {
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
    "Java Script": "",
    "Lua": "",
    "Kotlin": "",
    "Markdown": "",
    "PHP": "",
    "Properties": "",
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
    "Type Script": "",
    "Vim Script": "",
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

    Docs test
        >>> get_file_icon('Python')
        ''
        >>> get_file_icon('xx')
        ''
    """
    #     
    return FILE_ICONS.get(file_type, "")


if __name__ == "__main__":
    import doctest

    doctest.testmod(verbose=True)
