# -*- coding:utf-8 -*-
# The PIGIT terminal tool entry file.

from typing import Dict, List
import os, logging, textwrap

from plenty import get_console

from .log import setup_logging
from .config import Config
from .cmdparse.parser import command, argument, Namespace
from .const import (
    VERSION,
    REPOS_PATH,
    PIGIT_HOME,
    LOG_FILE_PATH,
    EXTRA_CMD_MODULE_NAME,
    EXTRA_CMD_MODULE_PATH,
    CONFIG_FILE_PATH,
    COUNTER_DIR_PATH,
    IS_FIRST_RUN,
)
from .common.utils import confirm
from .common.func import dynamic_default_attrs, time_it
from .gitlib.processor import ShortGitter, GIT_CMDS, get_extra_cmds
from .gitlib.options import GitOption
from .gitlib.ignore import create_gitignore
from .info import introduce, GitConfig


Logger = logging.getLogger(__name__)


# ===============
# Configuration.
# ===============
CONFIG = Config(
    path=CONFIG_FILE_PATH, version=VERSION, auto_load=True
).output_warnings()

setup_logging(
    debug=CONFIG.debug_open,
    log_file=None if CONFIG.log_output else LOG_FILE_PATH,
)


# ==============
# Global handle
# ==============
git = GitOption(repo_json_path=REPOS_PATH)
console = get_console()


# =====================
# main command `pigit`
# yapf: disable
# =====================
@command("pigit", description="Pigit TUI is called automatically if no parameters are followed.")
@argument("-r --report", action="store_true", help="Report the pigit desc and exit.")
@argument("-f --config", action="store_true", help="Display the config of current git repository and exit.")
@argument("-i --information", action="store_true", help="Show some information about the current git repository.")
def pigit(args: Namespace, _) -> None:
    if args.report:
        console.echo(introduce())

    elif args.create_config:
        return CONFIG.create_config_template()

    elif args.config:
        console.echo(GitConfig(format_type=CONFIG.git_config_format).generate())

    elif args.information:
        console.echo(git.get_repo_desc(include_part=CONFIG.repo_info_include))

    elif args.complete:
        # Generate competion vars dict.
        complete_vars = pigit.to_dict()
        complete_vars["args"]["cmd"]["args"].update(
            {k: {"help": v["help"], "args": {}} for k, v in GIT_CMDS.items()}
        )

        from .cmdparse.shellcompletion import shell_complete

        shell_complete(complete_vars, PIGIT_HOME, inject=True)
        return None

    elif args.ignore_type:
        _, msg = create_gitignore(args.ignore_type,writting=True)
        console.echo(msg)

    elif args.count:
        from .codecounter import CodeCounter

        path = os.path.abspath(args.count) if args.count != "." else os.getcwd()
        CodeCounter(
            count_path=path,
            use_ignore=CONFIG.counter_use_gitignore,
            result_saved_path=COUNTER_DIR_PATH,
            format_type=CONFIG.counter_format,
            use_icon=CONFIG.counter_show_icon,
        ).run(
            show_invalid=CONFIG.counter_show_invalid,
        )
        return None

    # Don't have invalid command list.
    # if not list(filter(lambda x: x, vars(known_args).values())):
    else:
        from .interaction import tui_main

        if IS_FIRST_RUN:
            introduce()
            if not confirm("Input `enter` to continue:"):
                return

        tui_main(help_wait=CONFIG.tui_help_showtime)


pigit.add_argument("-v", "--version", action="version", help="Show version and exit.", version=f"Version:{VERSION}")

tools_group = pigit.add_argument_group(title="tools arguments", description="Auxiliary type commands.")
tools_group.add_argument("-c", "--count", nargs="?", const=".", type=str, metavar="PATH",
    help="""Count the number of codes and output them in tabular form.
    A given path can be accepted, and the default is the current directory.
    """,)
tools_group.add_argument( "--create-ignore", type=str, metavar="TYPE", dest="ignore_type",
    help="""Create a demo .gitignore file. Need one argument, the type of gitignore.""")
tools_group.add_argument("-C", "--complete", action="store_true",
    help="Add shell prompt script and exit. (Supported bash, zsh, fish)")
tools_group.add_argument("--create-config", action="store_true",
    help="Create a pre-configured file of PIGIT."
    "(If a profile exists, the values available in it are used)",)

# =============================================
# sub command `cmd`
# =============================================
@pigit.sub_parser("cmd", help="git short command.")
@argument("--shell", action="store_true", help="Go to the pigit shell mode.")
@argument("-t --types", action="store_true", help="List all command types and exit.")
@argument("-p --show-part-command", type=str, metavar="TYPE", dest="command_type",
    help='According to given type to list available short command and wealth and exit.')
@argument("-s --show-commands", action="store_true", help="List all available short command and wealth and exit.")
@argument("args", nargs="*", type=str, help="Command parameter list.")
@argument("command", nargs="?", type=str, default=None, help="Short git command or other.")
def _cmd_func(args: Namespace, unknown: List):
    """If you want to use some original git commands, please use -- to indicate."""

    # If you want to manipulate the current folder with git,
    # try adding it to repos automatically.
    if CONFIG.repo_auto_append:
        repo_path, repo_conf = git.get_repo_info()
        git.add_repos([repo_path])

    # Init extra custom cmds.
    extra_cmd: Dict = {
        # "shell": {
        #     "command": lambda _: shell_mode(git_processor),
        #     "type": "func",
        #     "help": "Into PIGIT shell mode.",
        # },  # only for tips.
    }
    extra_cmd.update(get_extra_cmds(EXTRA_CMD_MODULE_NAME, EXTRA_CMD_MODULE_PATH))

    git_processor = ShortGitter(
        extra_cmds=extra_cmd,
        command_prompt=CONFIG.cmd_recommend,
        show_original=CONFIG.cmd_show_original,
    )

    if args.shell:
        from .shellmode import PigitShell
        shell_ = PigitShell(git_processor)
        # print(shell_.__dir__())
        shell_.cmdloop()
        return

    if args.show_commands:
        return git_processor.print_help()

    if args.command_type:
        return git_processor.print_help_by_type(args.command_type)

    if args.types:
        return git_processor.print_types()

    if args.command:
        command = args.command
        args.args.extend(unknown)
        git_processor.do(command, args.args)
        return None
    else:
        console.echo("`pigit cmd -h`<ok> for help.")


# =============================================
# sub command `repo`
# =============================================
repo = pigit.sub_parser("repo", help="repos options.")(lambda _, __: print("-h help"))


@repo.sub_parser("add", help="add repo(s).")
@argument("--dry-run", action="store_true", help="dry run.")
@argument("paths", nargs="+", help="path of reps(s).")
def repo_add(args, _):
    if added := git.add_repos(args.paths, args.dry_run):
        console.echo(f"Found {len(added)} new repo(s).")
        for path in added:
            console.echo(f"\t`{path}`<sky_blue>")
    else:
        console.echo("`No new repos found!`<tomato>")


@repo.sub_parser("rm", help="remove repo(s).")
@argument("--path", action="store_true", help="remove follow path, defult is name.")
@argument("repos", nargs="+", help="name or path of repo(s).")
def repo_rm(args, _):
    res = git.rm_repos(args.repos, args.path)
    for one in res:
        console.echo(f"Deleted repo. name: '{one[0]}', path: {one[1]}")


@repo.sub_parser("rename", help="rename a repo.")
@argument("new_name", help="the new name of repo.")
@argument("repo", help="the name of repo.")
def repo_rename(args, _):
    success, msg = git.rename_repo(args.repo, args.new_name)
    console.echo(msg)


@repo.sub_parser("ll", help="display summary of all repos.")
@argument("--simple", action="store_true", help="display simple summary.")
@argument("--revese", action="store_true", help="revese to display invalid repo.")
def repo_ll(args, _):
    simple = args.simple
    revese = args.revese

    for info in git.ll_repos(revese=revese):
        if simple:
            if revese:
                console.echo(f"{info[0][0]:<20} {info[1][1]:<15}")
            else:
                console.echo(f"{info[0][0]:<20} {info[1][1]:<15} {info[5][1]}")
        else:
            if revese:
                summary_string = textwrap.dedent(
                    f"""\
                    b`{info[0][0]}`
                        {info[1][0]}: `{info[1][1]}`<sky_blue>
                    """
                )
            else:
                summary_string = textwrap.dedent(
                    f"""\
                    b`{info[0][0]}`
                        {info[1][0]}: {info[1][1]}
                        {info[2][0]}: {info[2][1]}
                        {info[3][0]}: `{info[3][1]}`<khaki>
                        {info[4][0]}: `{info[4][1]}`<ok>
                        {info[5][0]}: `{info[5][1]}`<sky_blue>
                    """
                )
            console.echo(summary_string)


repo.sub_parser("clear", help="clear the all repos.")(lambda _, __: git.clear_repos())


repo_options = {
    "fetch": {"cmd": "git fetch", "allow_all": True, "help": "fetch remote update"},
    "pull": {"cmd": "git pull", "allow_all": True, "help": "pull remote updates"},
    "push": {"cmd": "git push", "allow_all": True, "help": "push the local updates"},
}
for subcmd, prop in repo_options.items():
    help_string = f'{h.strip()} for repo(s).' if (h:=prop.get("help")) else "NULL"
    repo.sub_parser(subcmd, help=help_string)(
        argument("repos", nargs="*", help="name of repo(s).")(
            dynamic_default_attrs(
                lambda args, _, cmd: git.process_repo_option(args.repos, cmd),
                cmd=prop['cmd']
            )
        )
    )


# =============================================
# sub command `open`
# =============================================
@pigit.sub_parser("open", help="open remote repository in web browser.")
@argument("-p --print", action="store_true", help="only print the url at the terminal, but do not open it.")
@argument("-c --commit", help="the current commit in the repo website.")
@argument("-i --issue", help="the given issue of the repository.")
@argument("branch", nargs="?", default=None, help="the branch of repository.")
def _open_func(args: Namespace, _):
    code, msg = git.open_repo_in_browser(
        branch=args.branch, issue=args.issue, commit=args.commit, print=args.print
    )
    console.echo(msg)


# =============================================
# terminal entry
# =============================================
@time_it
def main():
    try:
        pigit()
    except (KeyboardInterrupt, EOFError):
        raise SystemExit(0) from None
