# -*- coding:utf-8 -*-

import os
import re
import shutil
import textwrap
import logging
from typing import Optional

from .utils import exec_cmd, color_print
from .common import Fx, TermColor, Symbol
from .common.str_table import dTable

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
IS_GIT_REPOSITORY: bool = True if REPOSITORY_PATH else False


def _config_normal_output(conf: dict[str, dict]):
    for t, d in conf.items():
        print(TermColor.Red + f"[{t}]")
        for k, v in d.items():
            print(" " * 4 + TermColor.SkyBlue + k, end="")
            print("=" + Fx.italic + TermColor.MediumVioletRed + v + Fx.reset)


def _config_table_output(conf: dict[str, dict]):
    for sub in conf.values():
        for k, v in sub.items():
            sub[k] = f"{TermColor.Green}{v:<40}{Fx.rs}"

    tb = dTable(conf, title='Git Local Config')
    tb.print()


def output_git_local_config(style: str = "table") -> None:
    """Print the local config of current git repository."""

    if not IS_GIT_REPOSITORY:
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
        l = re.split(r"\r\n|\r|\n", context)
        l_len = len(l)
        config_dict = {}
        idx = 0

        while idx < l_len:
            if l[idx].startswith("["):
                config_type = l[idx][1:-1].strip()
                if not config_dict.get(config_type):
                    config_dict[config_type] = {}
                    idx += 1
                    while idx < l_len and not l[idx].startswith("["):
                        if "=" not in l[idx]:
                            idx += 1
                            continue
                        key, value = l[idx].split("=", 1)
                        config_dict[config_type][key.strip()] = value.strip()
                        idx += 1
        # print(config_dict)

        if style == "normal":
            _config_normal_output(config_dict)
        elif style == "table":
            _config_table_output(config_dict)
        else:
            _config_normal_output(config_dict)


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
