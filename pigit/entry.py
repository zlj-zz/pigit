# -*- coding:utf-8 -*-
# The PIGIT terminal tool entry file.

import os
from typing import TYPE_CHECKING, List

from plenty import get_console
from plenty.table import Table

from .config import Config
from .context import Context
from .const import (
    CMD_TYPE_LIST_SENTINEL,
    CONFIG_FILE_PATH,
    COUNTER_DIR_PATH,
    REPOS_PATH,
    VERSION,
)
from .cmdparse.parser import argument, command
from .ext.lcstat import LINES_CHANGE, LINES_NUM, FILES_CHANGE, FILES_NUM, Counter
from .ext.func import dynamic_default_attrs
from .ext.utils import get_file_icon
from .git import Git_Proxy_Cmds, create_gitignore
from .handlers import CmdHandler, RepoCommandHandler, TuiHandler
from .info import introduce, show_gitconfig

if TYPE_CHECKING:
    from .cmdparse.parser import Namespace


# ===============
# Configuration.
# ===============
conf = Config(path=CONFIG_FILE_PATH, version=VERSION, auto_load=True).output_warnings()


# ==============
# Global handle
# ==============
ctx = Context.bootstrap(config=conf, repo_json_path=REPOS_PATH)
Context.install(ctx)
console = get_console()


# =====================
# main command `pigit`
# yapf: disable
# =====================
@command("pigit", description="Pigit TUI is called automatically if no parameters are followed.")
@argument("-r --report", action="store_true", help="Report the pigit desc and exit.")
@argument("-f --config", action="store_true", help="Display the config of current git repository and exit.")
@argument("-i --information", action="store_true", help="Show some information about the current git repository.")
def pigit(args: "Namespace", _) -> None:
    if args.report:
        console.echo(introduce())

    elif args.create_config:
        ctx.config.create_config_template()
        return

    elif args.config:
        console.echo(show_gitconfig(format_type=ctx.config.git_config_format))

    elif args.information:
        console.echo(ctx.repo.get_repo_desc(include_part=ctx.config.repo_info_include))

    elif args.complete:
        # Generate completion vars dict.
        complete_vars = pigit.to_dict()
        complete_vars["args"]["cmd"]["args"].update(
            {k: {"help": v["help"], "args": {}} for k, v in Git_Proxy_Cmds.items()}
        )

        from .cmdparse.completion import shell_complete

        shell_complete(complete_vars, args.complete)
        return None

    elif args.ignore_type:
        _, msg = create_gitignore(args.ignore_type, writing=True)
        console.echo(msg)

    elif args.count:
        path = os.path.abspath(args.count) if args.count != "." else os.getcwd()
        total_size, diff_result, invalids = Counter(
            saved_dir=COUNTER_DIR_PATH, show_invalid=ctx.config.counter_show_invalid
        ).diff_count(path, ctx.config.counter_use_gitignore)
        if ctx.config.counter_format == "simple":
            for k, v in diff_result.items():
                print(f"::{k}  (files:{v[FILES_NUM]:,} | lines:{v[LINES_NUM]:,})")

        elif conf.counter_format == "table":

            def color_index(
                count: int,
            ) -> str:
                # Colors displayed for different code quantities.
                level_color = (
                    "green",
                    "#EBCB8C",  # yellow
                    "#FF6347",  # tomato
                    "#C71585",  # middle violet red
                    "#87CEFA",  # skyblue
                )
                index = len(str(count // 1000))
                return (
                    level_color[-1]
                    if index > len(level_color)
                    else level_color[index - 1]
                )

            tb = Table(title="[Code Counter Result]", title_style="bold")
            tb.add_column("Language")
            tb.add_column("Files")
            tb.add_column("Code lines")

            for k, v in diff_result.items():
                f_type_str = (
                    f"`{get_file_icon(k)} {k}`<cyan>"
                    if ctx.config.counter_show_icon
                    else k
                )

                f_num_str = f"`{v[FILES_NUM]}`<{color_index(v[FILES_NUM])}>"
                l_num_str = f"`{v[LINES_NUM]}`<{color_index(v[LINES_NUM])}>"

                f_change_str = (
                    f"{v[FILES_CHANGE]:+}" if v.get(FILES_CHANGE, 0) != 0 else ""
                )
                l_change_str = (
                    f"{v[LINES_CHANGE]:+}" if v.get(LINES_CHANGE, 0) != 0 else ""
                )

                tb.add_row(
                    f_type_str,
                    f"{f_num_str} `{f_change_str}`<{'#98fb98' if f_change_str.startswith('+') else '#ff6347'}>",
                    f"{l_num_str} `{l_change_str}`<{'#98fb98' if l_change_str.startswith('+') else '#ff6347'}>",
                )
            tb.caption = " Total: {0}".format(total_size)
            get_console().echo(tb)
        else:
            print("Invalid display format!")

        return None

    # Don't have invalid command list.
    # if not list(filter(lambda x: x, vars(known_args).values())):
    else:
        handler = TuiHandler(ctx)
        if handler.preprocess():
            handler.execute()


# yapf: enable
pigit.add_argument(
    "-v",
    "--version",
    action="version",
    help="Show version and exit.",
    version=f"Version:{VERSION}",
)

tools_group = pigit.add_argument_group(
    title="tools arguments", description="Auxiliary type commands."
)
tools_group.add_argument(
    "-c",
    "--count",
    nargs="?",
    const=".",
    type=str,
    metavar="PATH",
    help="""Count the number of codes and output them in tabular form.
    A given path can be accepted, and the default is the current directory.
    """,
)
tools_group.add_argument(
    "--create-ignore",
    type=str,
    metavar="TYPE",
    dest="ignore_type",
    help="""Create a demo .gitignore file. Need one argument, the type of gitignore.""",
)
tools_group.add_argument(
    "--complete",
    nargs="?",
    const="nil",
    type=str,
    metavar="SHELL",
    help="Add shell prompt script and exit. (Supported bash, zsh, fish)",
)
tools_group.add_argument(
    "--create-config",
    action="store_true",
    help="Create a pre-configured file of PIGIT."
    "(If a profile exists, the values available in it are used)",
)


# =============================================
# sub command `cmd`
# =============================================
@pigit.sub_parser("cmd", help="git short command.")
@argument("--shell", action="store_true", help="Go to the pigit shell mode.")
@argument(
    "-l --list",
    action="store_true",
    dest="cmd_list",
    help="List all short commands and help (full table).",
)
@argument(
    "-s --search",
    dest="cmd_search",
    nargs=1,
    metavar="QUERY",
    help="Search commands by keyword (substring, case-insensitive). "
    "For the complete table use -l / --list instead.",
)
@argument(
    "-p --pick",
    action="store_true",
    dest="cmd_pick",
    help="Interactively pick and run a short command (requires a TTY).",
)
@argument(
    "-t --type",
    nargs="?",
    const=CMD_TYPE_LIST_SENTINEL,
    default=None,
    dest="cmd_type",
    metavar="TYPE",
    help="Without TYPE: list supported command types. "
    "With TYPE: list short commands in that type (e.g. Branch).",
)
@argument("args", nargs="*", type=str, help="Command parameter list.")
@argument(
    "command", nargs="?", type=str, default=None, help="Short git command or other."
)
def _(args: "Namespace", unknown: List):
    """If you want to use some original git commands, please use -- to indicate."""

    CmdHandler(ctx.current(), args, unknown).execute()


# =============================================
# sub command `repo`
# =============================================
repo = pigit.sub_parser("repo", help="repos options.")(lambda _, __: print("-h help"))


@repo.sub_parser("add", help="add repo(s).")
@argument("--dry-run", action="store_true", help="dry run.")
@argument("paths", nargs="+", help="path of reps(s).")
def repo_add(args, _):
    RepoCommandHandler(ctx.current()).add(args)


@repo.sub_parser("rm", help="remove repo(s).")
@argument("--path", action="store_true", help="remove follow path, default is name.")
@argument("repos", nargs="+", help="name or path of repo(s).")
def repo_rm(args, _):
    RepoCommandHandler(ctx.current()).rm(args)


@repo.sub_parser("rename", help="rename a repo.")
@argument("new_name", help="the new name of repo.")
@argument("repo", help="the name of repo.")
def repo_rename(args, _):
    RepoCommandHandler(ctx.current()).rename(args)


@repo.sub_parser("ll", help="display summary of all repos.")
@argument("--simple", action="store_true", help="display simple summary.")
@argument("--reverse", action="store_true", help="reverse to display invalid repo.")
def repo_ll(args, _):
    RepoCommandHandler(ctx.current()).ll(args)


repo.sub_parser("clear", help="clear the all repos.")(
    lambda _, __: RepoCommandHandler(ctx.current()).clear()
)


@repo.sub_parser("report", help="genereate report of all repos.")
@argument("--author", type=str, required=True, help="select author of commits.")
@argument("--since",  type=str,default='', help="start range of commits.")
@argument("--until",  type=str,default='', help="end range of commits.")
def repo_report(args, _):
    RepoCommandHandler(ctx.current()).report(args)


@repo.sub_parser("cd", help="jump to a repo dir.")
@argument("repo", nargs="?", help="the name of repo.")
def _(args, _):
    RepoCommandHandler(ctx.current()).cd(args)


repo_options = {
    "fetch": {"cmd": "git fetch", "allow_all": True, "help": "fetch remote update"},
    "pull": {"cmd": "git pull", "allow_all": True, "help": "pull remote updates"},
    "push": {"cmd": "git push", "allow_all": True, "help": "push the local updates"},
}
for sub_cmd, prop in repo_options.items():
    help_string = f"{h.strip()} for repo(s)." if (h := prop.get("help")) else "NULL"
    repo.sub_parser(sub_cmd, help=help_string)(
        argument("repos", nargs="*", help="name of repo(s).")(
            dynamic_default_attrs(
                lambda args, _, cmd: RepoCommandHandler(
                    ctx.current()
                ).process_repos_option(args.repos, cmd),
                cmd=prop["cmd"],
            )
        )
    )


# =============================================
# sub command `open`
# yapf: disable
# =============================================
@pigit.sub_parser("open", help="open remote repository in web browser.")
@argument("-p --print", action="store_true", help="only print the url at the terminal, but do not open it.")
@argument("-c --commit", help="the current commit in the repo website.")
@argument("-i --issue", help="the given issue of the repository.")
@argument("branch", nargs="?", default=None, help="the branch of repository.")
def _(args: "Namespace", _):
    RepoCommandHandler(ctx.current()).open_browser(args)

# yapf: enable
