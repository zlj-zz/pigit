from __future__ import print_function
import subprocess
import logging

Log = logging.getLogger(__name__)


def run_cmd(*args):
    """Run system command.

    Returns:
        (bool): Wether run successful.

    >>> with subprocess.Popen("git status", shell=True) as proc:
    >>>    proc.wait()
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

    >>> proc = subprocess.Popen(
    ...    "git --version", stderr=subprocess.PIPE, stdout=subprocess.PIPE, shell=True
    ... )
    >>> res = proc.stdout.read().decode()
    >>> err = proc.stderr.read().decode()
    >>> print(err, res)
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

    >>> confirm('[y/n] (default: yes):')
    """
    input_command = input(text).strip().lower()
    if input_command in ["n", "no", "N", "No"]:
        return False
    elif input_command in ["y", "yes", "Y", "Yes"]:
        return True
    else:
        return default
