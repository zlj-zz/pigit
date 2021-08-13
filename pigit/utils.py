# -*- coding:utf-8 -*-

from __future__ import print_function, absolute_import
import os
import subprocess
import logging
from math import sqrt
from collections import Counter

from .compat import input

Log = logging.getLogger(__name__)

# Exit code.
EXIT_NORMAL = 0
EXIT_ERROR = 1


def leave(code, *args):
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


def run_cmd(*args):
    """Run system command.

    Returns:
        (bool): Wether run successful.

    >>> run_cmd('pwd')
    True
    >>> run_cmd('which', 'python')
    True
    """

    try:
        with subprocess.Popen(" ".join(args), shell=True) as proc:
            proc.wait()
        return True
    except Exception as e:
        Log.warning(e)
        return False


def exec_cmd(*args):
    """Run system command and get result.

    Returns:
        (str, str): Error string and result string.
    """

    try:
        proc = subprocess.Popen(
            " ".join(args), stderr=subprocess.PIPE, stdout=subprocess.PIPE, shell=True
        )
        res = proc.stdout.read().decode()
        err = proc.stderr.read().decode()
        proc.kill()
        return err, res
    except Exception as e:
        Log.warning(e)
        print(e)
        return e, ""


def confirm(text="", default=True):
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
    input_command = input(text).strip().lower()
    if input_command in ["n", "no", "N", "No"]:
        return False
    elif input_command in ["y", "yes", "Y", "Yes"]:
        return True
    else:
        return default


def similar_command(command, all_commands):
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
    words = {word: dict(Counter(word)) for word in all_commands}
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

    def _comparison_reciprocal(a, b):
        """
        Returns how many identical letters
        are compared from the head. sigmod
        to 0 ~ 1.

        Args:
            a (str): need compare string.
            b (str): need compare string.
        """
        i = 0
        while i < len(a) and i < len(b):
            if a[i] == b[i]:
                i += 1
            else:
                break
        return 1 / (i + 1)

    # The value of `frequency_sum_square` is multiplied by the weight to find
    # the minimum.
    # Distance weight: compensate for the effect of length difference.
    # Compare Weight: The more similar the beginning, the higher the weight.
    min_frequency_command = min(
        frequency_sum_square,
        key=lambda item: item[1]
        * (
            len(command) / len(item[0])
            if len(command) / len(item[0])
            else len(item[0]) / len(command)
        )
        * _comparison_reciprocal(command, item[0]),
    )[0]
    return min_frequency_command


def color_print(value, *styles, **options):
    """Print to terminal.

    Print special information with color and style according to the
    incoming parameters.

    Args:
        msg: A special message.
        style: Message style, like: [bold, underline].
    """
    _style = "".join(styles)
    end = options.get("end", "\n")
    value = "%s%s\033[0m" % (_style, value)
    print(value, end=end)


def dir_wether_ok(dir_path):
    """Determine whether the dir path exists. If not, create a directory.

    Args:
        dir_path (str): Directory path, like: "~/.config/xxx"

    >>> ensure_path('~/.config/pigit')
    """
    if os.path.isdir(dir_path):
        return True
    try:
        os.makedirs(dir_path, exist_ok=True)
        return True
    except Exception as e:
        return False


if __name__ == "__main__":
    import doctest

    doctest.testmod()
