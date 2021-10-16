# -*- coding:utf-8 -*-

import subprocess
import logging
from math import sqrt
from collections import Counter
from typing import Iterable, Tuple


Log = logging.getLogger(__name__)


def run_cmd(*args) -> bool:
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
    current_shell = ""
    _, resp = exec_cmd("echo $SHELL")
    if resp:
        current_shell = resp.split("/")[-1].strip()
    return current_shell.lower()


if __name__ == "__main__":
    import doctest

    doctest.testmod(verbose=True)

    print(get_current_shell())
