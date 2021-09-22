# -*- coding:utf-8 -*-

import os
import re
import shutil
import textwrap
import logging
from typing import Optional

from .utils import exec_cmd, color_print
from .common import Fx, TermColor

Log = logging.getLogger(__name__)


def git_version() -> str:
    """Get Git version."""
    _, git_version_ = exec_cmd("git --version")
    if git_version_:
        return git_version_
    else:
        return ""


# Not detected, the result is None
Git_Version: str = git_version()


def current_repository() -> str:
    """Get the current git repository path. If not, the path is empty."""
    err, path = exec_cmd("git rev-parse --git-dir")

    if err:
        return ""

    path = path.strip()
    if path == ".git":
        repository_path = os.getcwd()
    else:
        repository_path = path[:-5]
    return repository_path


REPOSITORY_PATH: str = current_repository()
IS_GIT_REOSITORY: bool = True if REPOSITORY_PATH else False


_header = (
    "========================================================================\n"
    "|{bold}{:^70}{unbold}|\n"
    "========================================================================"
)

_item = "| {:<25} | {value_color}{:<40}{reset} |"


def _config_normal_head_output(head: str):
    print(TermColor.Red + head)


def _config_normal_item_output(key: str, value: str):
    print(TermColor.SkyBlue + key, end="")
    print("=" + Fx.italic + TermColor.MediumVioletRed + value + Fx.reset)


def _config_normal_output_end():
    pass


def _config_table_head_output(head: str):
    print(_header.format(head[1:-1], bold=Fx.bold, unbold=Fx.unbold))


def _config_table_item_output(key: str, value: str):
    print(
        _item.format(
            key.strip(),
            value.strip(),
            value_color=TermColor.Green,
            reset=Fx.reset,
        )
    )


def _config_table_output_end():
    print("-" * 72)


def output_git_local_config(style: str = "table") -> None:
    """Print the local config of current git repository."""

    if not IS_GIT_REOSITORY:
        color_print("This directory is not a git repository yet.", TermColor.Red)
        return None

    _re = re.compile(r"\w+\s=\s.*?")
    width, _ = shutil.get_terminal_size()
    if width < 72:
        style = "normal"

    try:
        with open(REPOSITORY_PATH + "/.git/config", "r") as cf:
            context = cf.read()
    except Exception as e:
        color_print(
            "Error reading configuration file. {0}".format(str(e)), TermColor.Red
        )
    else:
        if style == "normal":
            _head_output = _config_normal_head_output
            _item_output = _config_normal_item_output
            _output_end = _config_normal_output_end
        elif style == "table":
            _head_output = _config_table_head_output
            _item_output = _config_table_item_output
            _output_end = _config_table_output_end
        else:
            _head_output = _config_normal_head_output
            _item_output = _config_normal_item_output
            _output_end = _config_normal_output_end

        for line in re.split(r"\r\n|\r|\n", context):
            if line.startswith("["):
                _head_output(line)
            else:
                if _re.search(line) is not None:
                    key, value = line.split("=")
                    _item_output(key, value)
        _output_end()


def output_repository_info(
    show_path: bool = True,
    show_remote: bool = True,
    show_branches: bool = True,
    show_lastest_log: bool = True,
    show_summary: bool = True,
) -> None:
    """Print some information of the repository.

    repository: `Repository_Path`
    remote: read from '.git/conf'
    >>> all_branch = run_cmd_with_resp('git branch --all --color')
    >>> lastest_log = run_cmd_with_resp('git log -1')
    """

    print("waiting ...", end="")

    error_str = TermColor.Red + "Error getting" + Fx.reset

    # Print content.
    print("\r[%s]        \n" % (Fx.b + "Repository Information" + Fx.reset,))
    if show_path:
        print(
            "Repository: \n\t%s\n" % (TermColor.SkyBlue + REPOSITORY_PATH + Fx.reset,)
        )

    # Get remote url.
    if show_remote:
        try:
            with open(REPOSITORY_PATH + "/.git/config", "r") as cf:
                config = cf.read()
        except Exception:
            remote = error_str
        else:
            res = re.findall(r"url\s=\s(.*)", config)
            remote = "\n".join(
                [
                    "\t%s%s%s%s" % (Fx.italic, TermColor.SkyBlue, x, Fx.reset)
                    for x in res
                ]
            )
        print("Remote: \n%s\n" % remote)

    # Get all branches.
    if show_branches:
        err, res = exec_cmd("git branch --all --color")
        if err:
            branches = "\t" + error_str
        else:
            branches = textwrap.indent(res, "\t")
        print("Branches: \n%s\n" % branches)

    # Get the lastest log.
    if show_lastest_log:
        err, res = exec_cmd("git log --stat --oneline --decorate -1 --color")
        if err:
            git_log = "\t" + error_str
        else:
            # git_log = "\n".join(["\t" + x for x in res.strip().split("\n")])
            git_log = textwrap.indent(res, "\t")
        print("Lastest log:\n%s\n" % git_log)

    # Get git summary.
    if show_summary:
        err, res = exec_cmd("git shortlog --summary --numbered")
        if err:
            summary = "\t" + error_str
        else:
            summary = textwrap.indent(res, "\t")
        print("Summary:\n%s\n" % summary)
