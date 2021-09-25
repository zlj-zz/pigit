# -*- coding:utf-8 -*-

import os
import re
import signal
import subprocess
import logging
from math import sqrt
from collections import Counter
from typing import Union, Iterable


Log = logging.getLogger(__name__)

# Exit code.
EXIT_NORMAL = 0
EXIT_ERROR = 1


def leave(code: int, *args) -> None:
    """Exit program.

    Receive error code, error message. If the error code matches, print the
    error information to the log. Then the command line output prompt, and
    finally exit.

    Args:
        code: Exit code.
        *args: Other messages.
    """

    if code == EXIT_ERROR:
        Log.error(args)

    raise SystemExit(0)


def run_cmd(*args) -> bool:
    """Run system command.

    Returns:
        (bool): Whether run successful.

    >>> run_cmd('pwd')
    True
    >>> run_cmd('which', 'python')
    True
    """

    try:
        # ? In python2, `subprocess` not support `with` sentence.
        proc = subprocess.Popen(" ".join(args), shell=True)
        proc.wait()
    except Exception as e:
        Log.error(str(e) + str(e.__traceback__))
        return False
    else:
        return True


def exec_cmd(*args) -> tuple[str, str]:
    """Run system command and get result.

    Returns:
        (str, str): Error string and result string.
    """

    try:
        # Take over the input stream and get the return information.
        proc = subprocess.Popen(
            " ".join(args),
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
            shell=True,
        )

        # Get normal output and error output.
        res = proc.stdout.read().decode()
        err = proc.stderr.read().decode()
        proc.kill()
    except Exception as e:
        Log.error(str(e) + str(e.__traceback__))
        return str(e), ""
    else:
        return err, res


def confirm(text: str = "", default: bool = True) -> bool:
    """Obtain confirmation results.
    Args:
        text (str): Confirmation prompt.
        default (bool): Result returned when unexpected input.

    Returns:
        (bool): Confirm result.

    >>> confirm()
    True
    >>> confirm(default=False)
    False
    """
    input_command: str = input(text).strip().lower()
    if input_command in ["n", "no", "N", "No"]:
        return False
    elif input_command in ["y", "yes", "Y", "Yes"]:
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

    >>> commands = ['branch', 'working tree', 'index', 'log', 'push', 'pull', 'tag','commit','conflict']
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
    frequency_difference = {
        word: [fre[ch] - words[word].get(ch, 0) for ch in command]
        + [words[word][ch] - fre.get(ch, 0) for ch in word]
        for word in words
    }
    # Square of sum of squares of word frequency difference.
    frequency_sum_square = list(
        map(
            lambda item: [item[0], sqrt(sum(map(lambda i: i ** 2, item[1])))],
            frequency_difference.items(),
        )
    )

    # The value of `frequency_sum_square` is multiplied by the weight to find
    # the minimum.
    # Distance weight: compensate for the effect of length difference.
    # Compare Weight: The more similar the beginning, the higher the weight.
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


def color_print(value: str, *styles, **options) -> None:
    """Print to terminal.

    Print special information with color and style according to the
    incoming parameters.

    Args:
        msg: A special message.
        style: Message style, like: [bold, underline].
    """

    value = "{0}{1}\033[0m".format("".join(styles), value)
    end = options.get("end", "\n")
    print(value, end=end)


Color_Re = re.compile(r"^#[0-9A-Za-z]{6}")


def is_color(s: Union[str, list, tuple, None]) -> bool:
    """Adjust `s` whether is color. Like: '#FF0000', [255, 0, 0], (0, 255, 0)

    >>> is_color('#FF0000')
    True
    >>> is_color([255, 0, 0])
    True
    >>> is_color((0, 255, 0))
    True
    >>> is_color(None)
    False
    >>> is_color(12345)
    False
    """
    if not s:
        return False
    elif type(s) == str:
        return True if Color_Re.match(s) else False
    elif isinstance(s, list) or isinstance(s, tuple):
        if len(s) != 3:
            return False
        else:
            for i in s:
                if i < 0 or i > 255:
                    return False
            else:
                return True
    else:
        return False


def dir_whether_ok(dir_path: str) -> bool:
    """Determine whether the dir path exists. If not, create a directory.

    Args:
        dir_path (str): Directory path, like: "~/.config/xxx"

    >>> dir_whether_ok('.')
    True
    """

    if os.path.isdir(dir_path):
        return True
    try:
        os.makedirs(dir_path, exist_ok=True)
    except Exception as e:
        Log.error(str(e) + str(e.__traceback__))
        return False
    else:
        return True


def init_hook():
    """Take over some system signals, which are used at
    the beginning of PIGIT.
    """
    try:
        signal.signal(signal.SIGINT, leave)
    except Exception as e:
        print(str(e))


if __name__ == "__main__":
    import doctest

    doctest.testmod()
