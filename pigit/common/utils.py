# -*- coding:utf-8 -*-

from typing import Callable, Iterable, Optional, Tuple
import sys
import platform
import subprocess
import asyncio
import logging
from math import sqrt
from collections import Counter


Log = logging.getLogger(__name__)


def traceback_info(extra_msg: str = "null"):
    """Get traceback infomation.

    Args:
        extra_msg (str, optional): extra custom message. Defaults to "null".

    Returns:
        str: formated traceback infomation.
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


def run_cmd(*args, cwd: Optional[str] = None) -> bool:
    """Run system command.

    Returns:
        (bool): Whether run successful.

    Docs test
        >>> run_cmd('pwd')
        True
        >>> run_cmd('which', 'python')
        True
    """

    try:
        # ? In python2, `subprocess` not support `with` sentence.
        proc = subprocess.Popen(" ".join(args), shell=True, cwd=cwd)
        proc.wait()
    except Exception as e:
        Log.error(traceback_info())
        return False
    else:
        return True


def exec_cmd(*args, cwd: Optional[str] = None) -> tuple[str, str]:
    """Run system command and get result.

    Returns:
        (str, str): Error string and result string.
    """

    try:
        # Take over the input stream and get the return information.
        with subprocess.Popen(
            " ".join(args),
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
            shell=True,
            cwd=cwd,
        ) as proc:

            output = proc.communicate()
            # Get normal output and error output.
            res = output[0].decode()
            err = output[1].decode()
            # res = proc.stdout.read().decode()
            # err = proc.stderr.read().decode()
    except Exception as e:
        Log.error(traceback_info())
        return str(e), ""
    else:
        return err, res


async def async_run_cmd(*args, cwd: Optional[str] = None, msg: Optional[str] = None):
    cmds = " ".join(args).split(" ")

    # receive (program, *args, ...), so must split the full cmd,
    # and unpack incoming.
    proc = await asyncio.create_subprocess_exec(
        *cmds,
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
        start_new_session=True,
        cwd=cwd,
    )
    res, err = await proc.communicate()

    msg and print(msg)
    res and print(res.decode())
    err and print(err.decode())

    if proc.returncode != 0:
        return cwd


def exec_async_tasks(tasks: list[Callable]) -> list[str]:
    """Execute tasks asynchronously."""

    # TODO: asyncio API is nicer in python 3.7
    if platform.system() == "Windows":
        loop = asyncio.ProactorEventLoop()
        asyncio.set_event_loop(loop)
    else:
        loop = asyncio.get_event_loop()

    try:
        errors = loop.run_until_complete(asyncio.gather(*tasks))
    finally:
        loop.close()
    return errors


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
            lambda item: (item[0], int(sqrt(sum(map(lambda i: i ** 2, item[1]))))),
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


def get_current_shell() -> str:
    """Gets the currently used shell.

    Returns:
            (str): Current shell string.
    """
    _, resp = exec_cmd("echo $SHELL")
    current_shell = resp.split("/")[-1].strip() if resp else ""
    return current_shell.lower()


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
    "properties": "Propertie",
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
    """

    if pre_type := SPECIAL_NAMES.get(file.lower(), None):
        return pre_type

    suffix = file.split(".")[-1]
    if suffix_type := SUFFIX_TYPE.get(suffix.lower(), None):
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
    """

    #     
    return FILE_ICONS.get(file_type, "")


if __name__ == "__main__":
    import doctest

    doctest.testmod(verbose=True)

    print(get_current_shell())

    try:
        a = int("abcd")
    except Exception as e:
        print(traceback_info())
    print(traceback_info())
