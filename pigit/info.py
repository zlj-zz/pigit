import os
import re
import textwrap

from pigit.const import __version__, __url__
from pigit.common import exec_cmd
from pigit.render import echo
from pigit.render.console import Console
from pigit.git_utils import get_git_version, get_repo_info
from pigit.render.table import TableTooWideError, dTable


def introduce() -> None:
    """Print the description information."""

    # Print version.
    print(
        """\
 ____ ___ ____ ___ _____
|  _ \\_ _/ ___|_ _|_   _|
| |_) | | |  _ | |  | |
|  __/| | |_| || |  | |
|_|  |___\\____|___| |_| version: {}
""".format(
            __version__
        )
    )

    # Print git version.
    git_version = get_git_version()
    if git_version is None:
        echo("`Don't found Git, maybe need install.`<error>")
    else:
        print(git_version)

    # Print package path.
    echo(
        "b`Local path`: u`{}`<sky_blue>\n".format(
            os.path.dirname(__file__.replace("./", ""))
        )
    )

    # Print description.
    echo(
        "b`Description:`\n"
        "  Terminal tool, help you use git more simple. Support Linux, MacOS and Windows.\n"
        f"  The open source path on github: u`{__url__}`<sky_blue>\n\n"
        "You can use `-h`<ok> or `--help`<ok> to get help and usage."
    )


##############
# Config info
##############
def parse_git_config(conf: str) -> dict:
    conf_list = re.split(r"\r\n|\r|\n", conf)
    config_dict: dict[str, dict[str, str]] = {}
    config_type: str = ""

    for line in conf_list:
        line = line.strip()

        if not line:
            continue

        elif line.startswith("["):
            config_type = line[1:-1].strip()
            config_dict[config_type] = {}

        elif "=" in line:
            key, value = line.split("=", 1)
            config_dict[config_type][key.strip()] = value.strip()

        else:
            continue

    return config_dict


def _config_normal_output(conf: dict[str, dict]) -> None:
    for t, d in conf.items():
        echo(f"`[{t}]`<tomato>")
        for k, v in d.items():
            echo(f"\t`{k}`<sky_blue>=`{v}`<medium_violet_red>")


def _config_table_output(conf: dict[str, dict]) -> None:
    for sub in conf.values():
        for k, v in sub.items():
            sub[k] = Console.render_str(f"`{v:40}`<pale_green>")

    tb = dTable(conf, title="Git Local Config")
    tb.print()


_output_way = {
    "normal": _config_normal_output,
    "table": _config_table_output,
}


def output_git_local_config(style: str = "table") -> None:
    """Print the local config of current git repository."""

    REPOSITORY_PATH, GIT_CONF_PATH = get_repo_info()

    if not REPOSITORY_PATH:
        echo("`This directory is not a git repository yet.`<error>")
        return None

    try:
        with open(f"{GIT_CONF_PATH}/config", "r") as cf:
            context = cf.read()
    except Exception as e:
        echo("`Error reading configuration file. {0}`<error>").format(str(e))
    else:
        config_dict = parse_git_config(context)

        try:
            _output_way[style](config_dict)
        except (KeyError, TableTooWideError) as e:
            # There are two different causes of errors that can be triggered here.
            # First, a non-existent format string is passed in (theoretically impossible),
            # but terminal does not have enough width to display the table.
            _output_way["normal"](config_dict)


def output_repository_info(include_part: list = None) -> None:
    """Print some information of the repository.

    repository: `Repository_Path`
    remote: read from '.git/conf'
    >>> all_branch = run_cmd_with_resp('git branch --all --color')
    >>> lastest_log = run_cmd_with_resp('git log -1')
    """

    print("waiting ...", end="")

    error_str = "`Error getting.`<error>"

    REPOSITORY_PATH, _ = get_repo_info()

    # Print content.
    echo("\r[b`Repository Information`]\n")
    if not include_part or "path" in include_part:
        echo(f"Repository: \n\t`{REPOSITORY_PATH}`<sky_blue>\n")

    # Get remote url.
    if not include_part or "remote" in include_part:
        try:
            with open(f"{REPOSITORY_PATH}/.git/config", "r") as cf:
                config = cf.read()
        except Exception:
            remote = error_str
        else:
            res = re.findall(r"url\s=\s(.*)", config)
            remote = "\n".join([f"\ti`{x}`<sky_blue>" for x in res])
        echo("Remote: \n%s\n" % remote)

    # Get all branches.
    if not include_part or "branch" in include_part:
        err, res = exec_cmd("git branch --all --color")
        branches = "\t" + error_str if err else textwrap.indent(res, "\t")
        print("Branches: \n%s\n" % branches)

    # Get the lastest log.
    if not include_part or "log" in include_part:
        err, res = exec_cmd("git log --stat --oneline --decorate -1 --color")
        git_log = "\t" + error_str if err else textwrap.indent(res, "\t")
        print("Lastest log:\n%s\n" % git_log)

    # Get git summary.
    if not include_part or "summary" in include_part:
        err, res = exec_cmd("git shortlog --summary --numbered")
        summary = "\t" + error_str if err else textwrap.indent(res, "\t")
        print("Summary:\n%s\n" % summary)
