# -*- coding:utf-8 -*-

import os
import re
import textwrap
import logging
from typing import Optional

from .utils import exec_cmd, color_print
from .common import Fx, TermColor

Log = logging.getLogger(__name__)


def git_version() -> Optional[str]:
    """Get Git version."""
    _, git_version_ = exec_cmd("git --version")
    if git_version_:
        return git_version_
    else:
        return None


# Not detected, the result is None
Git_Version: Optional[str] = git_version()


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


Repository_Path: str = current_repository()
IS_Git_Repository: bool = True if Repository_Path else False


def git_local_config() -> None:
    """Print the local config of current git repository."""
    if IS_Git_Repository:
        _re = re.compile(r"\w+\s=\s.*?")
        try:
            with open(Repository_Path + "/.git/config", "r") as cf:
                for line in re.split(r"\r\n|\r|\n", cf.read()):
                    if line.startswith("["):
                        print(TermColor.Red + line)
                    else:
                        if _re.search(line) is not None:
                            key, value = line.split("=")
                            print(TermColor.SkyBlue + key, end="")
                            print(
                                "="
                                + Fx.italic
                                + TermColor.MediumVioletRed
                                + value
                                + Fx.reset
                            )
        except Exception as e:
            color_print(
                "Error reading configuration file. {0}".format(str(e)), TermColor.Red
            )
    else:
        color_print("This directory is not a git repository yet.", TermColor.Red)


def repository_info(
    show_path: bool = True,
    show_remote: bool = True,
    show_branches: bool = True,
    show_lastest_log: bool = True,
    show_summary: bool = True,
) -> None:
    # type:(bool, bool, bool, bool, bool) -> None
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
            "Repository: \n\t%s\n" % (TermColor.SkyBlue + Repository_Path + Fx.reset,)
        )
    # Get remote url.
    if show_remote:
        try:
            with open(Repository_Path + "/.git/config", "r") as cf:
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
