# -*- coding:utf-8 -*-

import re
import textwrap
import logging

from .common import exec_cmd, render_str, traceback_info
from .common.git_utils import parse_git_config, git_version, current_repository
from .common.table import dTable, TableTooWideError

Log = logging.getLogger(__name__)


# Not detected, the result is empty str.
Git_Version: str = git_version()

# Not a repository, the all path is empty str.
REPOSITORY_PATH, GIT_CONF_PATH = current_repository()


def _config_normal_output(conf: dict[str, dict]) -> None:
    for t, d in conf.items():
        print(render_str(f"`[{t}]`<tomato>"))
        for k, v in d.items():
            print(render_str(f"\t`{k}`<sky_blue>=`{v}`<medium_violet_red>"))


def _config_table_output(conf: dict[str, dict]) -> None:
    for sub in conf.values():
        for k, v in sub.items():
            sub[k] = render_str(f"`{v:40}`<pale_green>")

    tb = dTable(conf, title="Git Local Config")
    tb.print()


output_way = {
    "normal": _config_normal_output,
    "table": _config_table_output,
}


def output_git_local_config(style: str = "table") -> None:
    """Print the local config of current git repository."""

    if not REPOSITORY_PATH:
        print(render_str("`This directory is not a git repository yet.`<error>"))
        return None

    try:
        with open(GIT_CONF_PATH + "/config", "r") as cf:
            context = cf.read()
    except Exception as e:
        print(
            render_str("`Error reading configuration file. {0}`<error>").format(str(e))
        )
    else:
        config_dict = parse_git_config(context)

        try:
            output_way[style](config_dict)
        except (KeyError, TableTooWideError) as e:
            # There are two different causes of errors that can be triggered here.
            # First, a non-existent format string is passed in (theoretically impossible),
            # but terminal does not have enough width to display the table.
            output_way["normal"](config_dict)

            # log error info.
            Log.error(traceback_info())


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

    error_str = render_str("`Error getting.`<error>")

    # Print content.
    print(render_str("\r[b`Repository Information`]\n"))
    if show_path:
        print(render_str(f"Repository: \n\t`{REPOSITORY_PATH}`<sky_blue>\n"))

    # Get remote url.
    if show_remote:
        try:
            with open(REPOSITORY_PATH + "/.git/config", "r") as cf:
                config = cf.read()
        except Exception:
            remote = error_str
        else:
            res = re.findall(r"url\s=\s(.*)", config)
            remote = "\n".join([render_str(f"\ti`{x}`<sky_blue>") for x in res])
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
