# The PIGIT terminal tool entry file.
from __future__ import annotations

import os
from typing import TYPE_CHECKING

from .config import get_config
from .context import Context
from .const import (
    CONFIG_FILE_PATH,
    COUNTER_DIR_PATH,
    REPOS_PATH,
    VERSION,
)
from .cmdparse.parser import argument, command

if TYPE_CHECKING:
    from .cmdparse.parser import Namespace


_TOOLS_GROUP = "tools"


def _bootstrap_config() -> Context:
    """Module-level bootstrap: config + Context only (no git probes).

    The repo layer (``before_hook`` auto-append) and the TUI key overrides
    are deferred to :func:`_ensure_repo_bootstrap` / the TUI branch, so
    light commands like ``-v`` neither probe the repository nor import termui.
    """
    conf = get_config(
        path=CONFIG_FILE_PATH, version=VERSION, auto_load=True
    ).output_warnings()
    ctx = Context.bootstrap(config=conf, repo_json_path=REPOS_PATH)
    Context.install(ctx)
    return ctx


ctx = _bootstrap_config()

_repo_bootstrapped = False


def _ensure_repo_bootstrap() -> None:
    """Run the repo-layer bootstrap (auto-append) once, on demand.

    Only repo-touching commands (TUI / counter / repo) reach this; ``-v``
    and config/report/create_config never probe git here.
    """
    global _repo_bootstrapped
    if _repo_bootstrapped:
        return
    _repo_bootstrapped = True
    from .hook import before_hook

    before_hook(ctx)


def _repo_handler():
    """Build the repo command handler, running the deferred repo bootstrap."""
    from .handlers import RepoCommandHandler

    _ensure_repo_bootstrap()
    return RepoCommandHandler(ctx.current())


def _color_index(count: int) -> str:
    """Return a color name based on code quantity (thousands)."""
    level_color = (
        "green",
        "#EBCB8C",  # yellow
        "#FF6347",  # tomato
        "#C71585",  # middle violet red
        "#87CEFA",  # skyblue
    )
    index = len(str(count // 1000))
    return level_color[-1] if index > len(level_color) else level_color[index - 1]


@command(
    "pigit",
    description="Pigit TUI is called automatically if no parameters are followed.",
    groups={
        _TOOLS_GROUP: {
            "title": "tools arguments",
            "description": "Auxiliary type commands.",
        }
    },
)
@argument(
    "-v --version",
    action="version",
    version=f"Version:{VERSION}",
    help="Show version and exit.",
)
@argument("-r --report", action="store_true", help="Report the pigit desc and exit.")
@argument(
    "-f --config",
    action="store_true",
    help="Display the config of current git repository and exit.",
)
@argument(
    "-i --information",
    action="store_true",
    help="Show some information about the current git repository.",
)
@argument(
    "-c --count",
    nargs="?",
    const=".",
    type=str,
    metavar="PATH",
    group=_TOOLS_GROUP,
    help="""Count the number of codes and output them in tabular form.
    A given path can be accepted, and the default is the current directory.
    """,
)
@argument(
    "--create-ignore",
    type=str,
    metavar="TYPE",
    dest="ignore_type",
    group=_TOOLS_GROUP,
    help="""Create a demo .gitignore file. Need one argument, the type of gitignore.""",
)
@argument(
    "--init",
    nargs="?",
    const="nil",
    type=str,
    metavar="SHELL",
    group=_TOOLS_GROUP,
    help="Add shell prompt script and exit. (Supported bash, zsh, fish)",
)
@argument(
    "--create-config",
    action="store_true",
    group=_TOOLS_GROUP,
    help="Create a pre-configured file of PIGIT."
    "(If a profile exists, the values available in it are used)",
)
@argument(
    "--with-keybindings",
    action="store_true",
    dest="with_keybindings",
    group=_TOOLS_GROUP,
    help="Dump commented default keys into the generated [app.keybindings] block."
    " (requires --create-config)",
)
def pigit(args: Namespace, _) -> None:
    if args.init:
        from .init import run_shell_init

        run_shell_init(args.init, pigit)
        return None

    elif args.create_config:
        from .app_keybindings import (
            collect_all_action_bindings,
            render_keybindings_template,
            warn_unmatched_keybindings,
        )

        bindings = collect_all_action_bindings()
        current = ctx.config.get().app.keybindings
        warn_unmatched_keybindings(bindings, current)
        block = render_keybindings_template(
            bindings, current, include_defaults=args.with_keybindings
        )
        ctx.config.create_config_template(keybindings_block=block)
        return

    from .termui.cli_output import get_console

    console = get_console()

    if args.report:
        from .info import introduce

        console.echo(introduce())

    elif args.config:
        from .ext.utils import page_output
        from .info import show_gitconfig

        page_output(console.render(show_gitconfig()))

    elif args.information:
        console.echo(
            ctx.git_api.get_repo_desc(include_part=ctx.config.get().info.repo_include)
        )

    elif args.ignore_type:
        from .git import create_gitignore

        _, msg = create_gitignore(args.ignore_type, writing=True)
        console.echo(msg)

    elif args.count:
        from .ext.lcstat import (
            LINES_CHANGE,
            LINES_NUM,
            FILES_CHANGE,
            FILES_NUM,
            Counter,
        )
        from .ext.utils import resolve_icon, resolve_nerd_icons

        _ensure_repo_bootstrap()
        path = os.path.abspath(args.count) if args.count != "." else os.getcwd()
        config = ctx.config.get()
        total_size, diff_result, invalids = Counter(
            saved_dir=COUNTER_DIR_PATH, show_invalid=config.counter.show_invalid
        ).diff_count(path, config.counter.use_gitignore)
        if config.counter.format == "simple":
            for k, v in diff_result.items():
                print(f"::{k}  (files:{v[FILES_NUM]:,} | lines:{v[LINES_NUM]:,})")

        elif config.counter.format == "table":
            console.echo(" @bold(Code Counter Result)")
            console.echo(" " + "-" * 50)

            # Pre-compute column widths for alignment.
            max_f_num = max(len(str(v[FILES_NUM])) for v in diff_result.values())
            max_l_num = max(len(str(v[LINES_NUM])) for v in diff_result.values())
            max_f_chg = max(
                (len(f"{v[FILES_CHANGE]:+}") if v.get(FILES_CHANGE, 0) != 0 else 0)
                for v in diff_result.values()
            )
            max_l_chg = max(
                (len(f"{v[LINES_CHANGE]:+}") if v.get(LINES_CHANGE, 0) != 0 else 0)
                for v in diff_result.values()
            )
            # Resolve once outside the loop; icon choice is per-render-strategy.
            nerd = resolve_nerd_icons(config.app.icons)

            for k, v in diff_result.items():
                f_type_str = (
                    f"@cyan({resolve_icon(nerd, k)} {k})"
                    if config.counter.show_icon
                    else k
                )

                f_color = _color_index(v[FILES_NUM])
                l_color = _color_index(v[LINES_NUM])

                # Align numbers as plain text, then wrap with color markup.
                f_num_raw = str(v[FILES_NUM]).rjust(max_f_num)
                l_num_raw = str(v[LINES_NUM]).rjust(max_l_num)
                f_num_str = f"@{f_color}({f_num_raw})"
                l_num_str = f"@{l_color}({l_num_raw})"

                f_change_raw = (
                    f"{v[FILES_CHANGE]:+}" if v.get(FILES_CHANGE, 0) != 0 else ""
                )
                l_change_raw = (
                    f"{v[LINES_CHANGE]:+}" if v.get(LINES_CHANGE, 0) != 0 else ""
                )

                f_change_color = (
                    "#98fb98" if f_change_raw.startswith("+") else "#ff6347"
                )
                l_change_color = (
                    "#98fb98" if l_change_raw.startswith("+") else "#ff6347"
                )

                # Fixed-width change columns so later columns stay aligned.
                if f_change_raw:
                    f_chg_pad = " " * (max_f_chg - len(f_change_raw))
                    f_change_part = f" @{f_change_color}({f_change_raw}){f_chg_pad}"
                else:
                    f_change_part = " " * (max_f_chg + 1) if max_f_chg else ""

                if l_change_raw:
                    l_chg_pad = " " * (max_l_chg - len(l_change_raw))
                    l_change_part = f" @{l_change_color}({l_change_raw}){l_chg_pad}"
                else:
                    l_change_part = " " * (max_l_chg + 1) if max_l_chg else ""

                console.echo(
                    f" {f_type_str:<20}  {f_num_str}{f_change_part}  "
                    f"{l_num_str}{l_change_part}"
                )

            console.echo(" " + "-" * 50)
            console.echo(f" Total: {total_size}")
        else:
            print("Invalid display format!")

        return None

    else:
        from .termui import set_key_overrides
        from .handlers import TuiHandler

        _ensure_repo_bootstrap()
        set_key_overrides(ctx.config.get().app.keybindings)
        handler = TuiHandler(ctx)
        if handler.preprocess():
            handler.execute()


# =============================================
# sub command `cmd`
# =============================================
@pigit.sub_parser("cmd", help="git short command system.")
@argument(
    "-l --list",
    action="store_true",
    help="List all commands.",
)
@argument(
    "-d --dangerous",
    action="store_true",
    help="List only dangerous commands.",
)
@argument(
    "-t --type",
    dest="type",
    metavar="CATEGORY",
    help="Filter by category (branch, commit, index, etc.).",
)
@argument(
    "-s --search",
    dest="search",
    metavar="QUERY",
    help="Search commands by keyword.",
)
@argument(
    "-p --pick",
    dest="pick",
    metavar="CATEGORY",
    nargs="?",
    const=True,
    help="Interactively pick and run a command (requires a TTY). Optional CATEGORY to filter.",
)
@argument(
    "--pick-print",
    dest="pick_print",
    metavar="CATEGORY",
    nargs="?",
    const=True,
    help="Interactively pick a command and print it to stdout instead of running.",
)
@argument(
    "--widget",
    choices=("bash", "zsh", "fish"),
    help="Print a shell widget for Alt+G picker integration.",
)
@argument(
    "command",
    nargs="*",
    help="Command to execute with arguments.",
)
def _(args: Namespace, _):
    """Execute short git commands."""
    from .handlers.cmd_handler import handle_cmd

    exit_code = handle_cmd(args)
    if exit_code != 0:
        raise SystemExit(exit_code)


# =============================================
# sub command `repo`
# =============================================
repo = pigit.sub_parser("repo", help="repos options.")(lambda _, __: repo.print_help())


@repo.sub_parser("add", help="add repo(s).")
@argument("--dry-run", action="store_true", help="dry run.")
@argument("paths", nargs="+", help="path of reps(s).")
def repo_add(args, _):
    _repo_handler().add(args)


@repo.sub_parser("rm", help="remove repo(s).")
@argument("--path", action="store_true", help="remove follow path, default is name.")
@argument("repos", nargs="+", arg_completion="repos", help="name or path of repo(s).")
def repo_rm(args, _):
    _repo_handler().rm(args)


@repo.sub_parser("update", help="refresh cached metadata for repo(s).")
@argument(
    "repos",
    nargs="*",
    arg_completion="repos",
    help="name(s) of repo(s) to refresh. refreshes all if omitted.",
)
def repo_update(args, _):
    _repo_handler().update(args)


@repo.sub_parser("rename", help="rename a repo.")
@argument("new_name", help="the new name of repo.")
@argument("repo", arg_completion="repos", help="the name of repo.")
def repo_rename(args, _):
    _repo_handler().rename(args)


@repo.sub_parser("ll", help="display summary of all repos.")
@argument("--simple", action="store_true", help="display simple summary.")
@argument("--reverse", action="store_true", help="reverse to display invalid repo.")
@argument("filter", nargs="?", default="", help="filter repos by fuzzy name match.")
def repo_ll(args, _):
    _repo_handler().ll(args)


@repo.sub_parser("clear", help="clear the all repos.")
def repo_clear(_, __):
    _repo_handler().clear()


@repo.sub_parser("report", help="genereate report of all repos.")
@argument("--author", type=str, required=True, help="select author of commits.")
@argument("--since", type=str, default="", help="start range of commits.")
@argument("--until", type=str, default="", help="end range of commits.")
def repo_report(args, _):
    _repo_handler().report(args)


@repo.sub_parser("cd", help="jump to a repo dir.")
@argument(
    "-p --pick",
    action="store_true",
    dest="repo_cd_pick",
    help="Interactive picker (TTY only). Exact repo name still cds without TUI.",
)
@argument(
    "--output-file",
    dest="repo_cd_output_file",
    default=None,
    help="Write the selected repo path to FILE instead of spawning a shell.",
)
@argument("repo", nargs="?", arg_completion="repos", help="the name of repo.")
def _(args, _):
    _repo_handler().cd(args)


@repo.sub_parser("mkbranch", help="batch create new branch across managed repos.")
@argument("branch_name", help="name of the new branch.")
@argument(
    "repos",
    nargs="*",
    arg_completion="repos",
    help="target repo names (interactive picker if omitted).",
)
@argument(
    "-c --checkout", action="store_true", help="checkout the new branch after creation."
)
@argument(
    "-b --base", type=str, default=None, help="create from specified base branch."
)
@argument("-f --force", action="store_true", help="reset branch if already exists.")
@argument("--dry-run", action="store_true", help="preview only, do not execute.")
@argument(
    "--filter-regex", type=str, default="", help="pre-filter repos in interactive mode."
)
def repo_mkbranch(args, _):
    _repo_handler().mkbranch(args)


@repo.sub_parser("switch", help="batch switch branch across managed repos.")
@argument("branch_name", help="name of the branch to switch to.")
@argument(
    "repos",
    nargs="*",
    arg_completion="repos",
    help="target repo names (interactive picker if omitted).",
)
@argument(
    "-c --create", action="store_true", help="create branch if it does not exist."
)
@argument(
    "-f --force", action="store_true", help="discard local changes when switching."
)
@argument("--dry-run", action="store_true", help="preview only, do not execute.")
@argument(
    "--filter-regex", type=str, default="", help="pre-filter repos in interactive mode."
)
def repo_switch(args, _):
    _repo_handler().switch(args)


repo_options = {
    "fetch": {"cmd": "git fetch", "allow_all": True, "help": "fetch remote update"},
    "pull": {"cmd": "git pull", "allow_all": True, "help": "pull remote updates"},
    "push": {"cmd": "git push", "allow_all": True, "help": "push the local updates"},
}


def _bulk_cmd_handler(cmd: str):
    """Build a repo sub-command handler with ``cmd`` baked in.

    The parser calls handlers as ``(args, parser_self)``; bulk_cmd needs the
    pre-configured git command string from ``repo_options``.
    """

    def handler(args, _parser):
        _repo_handler().bulk_cmd(args, cmd)

    return handler


for sub_cmd, prop in repo_options.items():
    help_string = f"{h.strip()} for repo(s)." if (h := prop.get("help")) else "NULL"
    repo.sub_parser(sub_cmd, help=help_string)(
        argument("repos", nargs="*", arg_completion="repos", help="name of repo(s).")(
            _bulk_cmd_handler(prop["cmd"])
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
def _(args: Namespace, _):
    from .handlers import OpenHandler

    OpenHandler(ctx.current()).open_browser(args)

# yapf: enable
