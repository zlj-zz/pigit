# -*- coding:utf-8 -*-
# The PIGIT terminal tool entry file.

from typing import TYPE_CHECKING, Dict, List, Optional
import os, logging

from .log import setup_logging
from .decorator import time_it
from .config import Config
from .argparse_utils import Parser
from .const import (
    REPOS_PATH,
    __version__,
    PIGIT_HOME,
    EXTRA_CMD_MODULE_NAME,
    EXTRA_CMD_MODULE_PATH,
    LOG_FILE_PATH,
    CONFIG_FILE_PATH,
    COUNTER_DIR_PATH,
    IS_FIRST_RUN,
)
from .render import get_console
from .common.utils import get_current_shell, confirm
from .common.git import GitOption
from .gitignore import GitignoreGenetor, SUPPORTED_GITIGNORE_TYPES
from .processor import CmdProcessor, Git_Cmds, CommandType, get_extra_cmds
from .info import introduce, GitConfig

if TYPE_CHECKING:
    import argparse


Log = logging.getLogger(__name__)


#################
# Configuration.
#################
CONFIG = Config(
    path=CONFIG_FILE_PATH, version=__version__, auto_load=True
).output_warnings()


git = GitOption(repo_info_path=REPOS_PATH)
console = get_console()


##########################################
# Implementation of additional functions.
##########################################
def shell_mode(git_processor: CmdProcessor):

    print(
        "Welcome come PIGIT shell.\n"
        "You can use short commands directly. Input '?' to get help.\n"
    )

    stopping: bool = False

    while not stopping:
        if not (input_argv_str := input("(pigit)> ").strip()):
            continue

        # Explode command string.
        argv = input_argv_str.split(maxsplit=1)
        command = argv[0]
        args_str = argv[1] if len(argv) == 2 else ""

        # Process.
        if command in ["quit", "exit"]:  # ctrl+c
            stopping = True

        elif command in git_processor.cmds.keys():
            git_processor.process_command(command, args_str.split())

        elif command in ["sh", "shell"]:
            if args_str:
                os.system(args_str)
            else:
                print("pigit shell: Please input shell command.")

        elif command == "?":
            if not args_str:
                print(
                    "Options:\n"
                    "  quit, exit      Exit the pigit shell mode.\n"
                    "  sh, shell       Run a shell command.\n"
                    "  tomato          It's a terminal tomato clock.\n"
                    "  ? [comand...]   Show help message. Use `? ?` to look detail.\n"
                )

            elif "?" in args_str:
                print(
                    "? is a tip command."
                    "Use `?` to look pigit shell options."
                    "Use `? [command...]` to look option help message.\n"
                    "Like:\n"
                    "`? sh` to get the help of sh command.\n"
                    "`? all` to get all support git quick command help.\n"
                    "Or `? ws ls` to get the help you want.\n"
                )

            elif "all" in args_str:
                git_processor.command_help()

            elif "sh" in args_str or "shell" in args_str:
                print(
                    "This command is help you to run a normal terminal command in pigit shell.\n"
                    "For example, you can use `sh ls` to check the files of current dir.\n"
                )

            else:
                invalid = []

                for item in args_str.split():
                    if item in git_processor.cmds.keys():
                        print(git_processor._generate_help_by_key(item))
                    else:
                        invalid.append(item)

                if invalid:
                    print("Cannot find command: {0}".format(",".join(invalid)))

        else:
            print(
                "pigit shell: Invalid command `{0}`, please select from "
                "[shell, tomato, quit] or git short command.".format(command)
            )

    return None


def _cmd_func(args: "argparse.Namespace", unknown: List, kwargs: Dict):
    # If you want to manipulate the current folder with git,
    # try adding it to repos automatically.
    if CONFIG.repo_auto_append:
        repo_path, repo_conf = git.get_repo_info()
        git.add_repos([repo_path])

    extra_cmd: dict = {
        "shell": {
            "command": lambda _: shell_mode(git_processor),
            "type": "func",
            "help": "Into PIGIT shell mode.",
        },  # only for tips.
    }
    extra_cmd.update(get_extra_cmds(EXTRA_CMD_MODULE_NAME, EXTRA_CMD_MODULE_PATH))

    git_processor = CmdProcessor(
        extra_cmds=extra_cmd,
        command_prompt=CONFIG.cmd_recommend,
        show_original=CONFIG.cmd_show_original,
    )

    if args.shell:
        shell_mode(git_processor)

    if args.show_commands:
        return git_processor.command_help()

    if args.command_type:
        return git_processor.command_help_by_type(args.command_type)

    if args.types:
        return git_processor.type_help()

    if args.command:
        command = args.command
        args.args.extend(unknown)
        git_processor.process_command(command, args.args)
        return None
    else:
        console.echo("`pigit cmd -h`<ok> for help.")


def _repo_func(args: "argparse.Namespace", unknown: List, kwargs: Dict):
    option: str = kwargs.get("option", "")

    if option == "add":
        if added := git.add_repos(args.paths, args.dry_run):
            console.echo(f"Found {len(added)} new repo(s).")
            for path in added:
                console.echo(f"\t`{path}`<sky_blue>")
        else:
            console.echo("`No new repos found!`<tomato>")
    elif option == "rm":
        res = git.rm_repos(args.repos, args.path)
        for one in res:
            console.echo(f"Deleted repo. name: '{one[0]}', path: {one[1]}")
    elif option == "rename":
        success, msg = git.rename_repo(args.repo, args.new_name)
        console.echo(msg)
    elif option == "ll":
        for info in git.ll_repos():
            if args.simple:
                console.echo(f"{info[0][0]:<20} {info[1][1]:<15} {info[5][1]}")
            else:
                console.echo(
                    f"""\
{info[0][0]}
    {info[1][0]}: {info[1][1]}
    {info[2][0]}: {info[2][1]}
    {info[3][0]}: `{info[3][1]}`<khaki>
    {info[4][0]}: `{info[4][1]}`<ok>
    {info[5][0]}: `{info[5][1]}`<sky_blue>
                    """
                )
    elif option == "clear":
        git.clear_repos()
    else:
        git.process_repo_option(args.repos, repo_options[option]["cmd"])


def _open_func(args: "argparse.Namespace", unknown: List, kwargs: Dict):
    code, msg = git.open_repo_in_browser(
        branch=args.branch, issue=args.issue, commit=args.commit, print=args.print
    )
    console.echo(msg)


repo_options = {
    "fetch": {"cmd": "git fetch", "allow_all": True, "help": "fetch remote update"},
    "pull": {"cmd": "git pull", "allow_all": True, "help": "pull remote updates"},
    "push": {"cmd": "git push", "allow_all": True, "help": "push the local updates"},
}

argparse_dict = {
    "prog": "pigit",
    "prefix_chars": "-",
    "description": "Pigit TUI is called automatically if no parameters are followed.",
    "args": {
        "-v --version": {
            "action": "version",
            "help": "Show version and exit.",
            "version": f"Version: {__version__}",
        },
        "-r --report": {
            "action": "store_true",
            "help": "Report the pigit desc and exit.",
        },
        "-f --config": {
            "action": "store_true",
            "help": "Display the config of current git repository and exit.",
        },
        "-i --information": {
            "action": "store_true",
            "help": "Show some information about the current git repository.",
        },
        "-d --debug": {
            "action": "store_true",
            "help": "Current runtime in debug mode.",
        },
        "--out-log": {"action": "store_true", "help": "Print log to console."},
        "-groups": {
            "tools": {
                "title": "tools arguments",
                "description": "Auxiliary type commands.",
                "args": {
                    "-c --count": {
                        "nargs": "?",
                        "const": ".",
                        "type": str,
                        "metavar": "PATH",
                        "help": "Count the number of codes and output them in tabular form."
                        "A given path can be accepted, and the default is the current directory.",
                    },
                    "-C --complete": {
                        "action": "store_true",
                        "help": "Add shell prompt script and exit.(Supported bash, zsh, fish)",
                    },
                    "--create-ignore": {
                        "type": str,
                        "metavar": "TYPE",
                        "dest": "ignore_type",
                        "help": f'Create a demo .gitignore file. Need one argument, support: [{", ".join(SUPPORTED_GITIGNORE_TYPES)}]',
                    },
                    "--create-config": {
                        "action": "store_true",
                        "help": "Create a pre-configured file of PIGIT."
                        "(If a profile exists, the values available in it are used)",
                    },
                },
            }
        },
        "cmd": {
            "help": "git short command.",
            "description": "If you want to use some original git commands, please use -- to indicate.",
            "args": {
                "command": {
                    "nargs": "?",
                    "type": str,
                    "default": None,
                    "help": "Short git command or other.",
                },
                "args": {
                    "nargs": "*",
                    "type": str,
                    "help": "Command parameter list.",
                },
                "-s --show-commands": {
                    "action": "store_true",
                    "help": "List all available short command and wealth and exit.",
                },
                "-p --show-part-command": {
                    "type": str,
                    "metavar": "TYPE",
                    "dest": "command_type",
                    "help": f'According to given type [{", ".join(CommandType.__members__.keys())}] list available short command and wealth and exit.',
                },
                "-t --types": {
                    "action": "store_true",
                    "help": "List all command types and exit.",
                },
                "--shell": {
                    "action": "store_true",
                    "help": "Go to the pigit shell mode.",
                },
                "set_defaults": {"func": _cmd_func},
            },
        },
        "repo": {
            "help": "repo options.",
            "args": {
                "add": {
                    "help": "add repo(s).",
                    "args": {
                        "paths": {"nargs": "+", "help": "path of reps(s)."},
                        "--dry-run": {
                            "action": "store_true",
                            "help": "dry run.",
                        },
                        "set_defaults": {
                            "func": _repo_func,
                            "kwargs": {"option": "add"},
                        },
                    },
                },
                "rm": {
                    "help": "remove repo(s).",
                    "args": {
                        "repos": {
                            "nargs": "+",
                            "help": "name or path of repo(s).",
                        },
                        "--path": {
                            "action": "store_true",
                            "help": "remove follow path, defult is name.",
                        },
                        "set_defaults": {
                            "func": _repo_func,
                            "kwargs": {"option": "rm"},
                        },
                    },
                },
                "rename": {
                    "help": "rename a repo.",
                    "args": {
                        "repo": {"help": "the name of repo."},
                        "new_name": {"help": "the new name of repo."},
                        "set_defaults": {
                            "func": _repo_func,
                            "kwargs": {"option": "rename"},
                        },
                    },
                },
                "ll": {
                    "help": "display summary of all repos.",
                    "args": {
                        "--simple": {
                            "action": "store_true",
                            "help": "display simple summary.",
                        },
                        "set_defaults": {
                            "func": _repo_func,
                            "kwargs": {"option": "ll"},
                        },
                    },
                },
                "clear": {
                    "help": "clear the all repos.",
                    "args": {
                        "set_defaults": {
                            "func": _repo_func,
                            "kwargs": {"option": "clear"},
                        },
                    },
                },
                **{
                    name: {
                        "help": prop["help"] + " for repo(s).",
                        "args": {
                            "repos": {
                                "nargs": "*",
                                "help": "name of repo(s).",
                            },
                            "set_defaults": {
                                "func": _repo_func,
                                "kwargs": {"option": name},
                            },
                        },
                    }
                    for name, prop in repo_options.items()
                },
            },
        },
        "open": {
            "help": "open remote repository in web browser.",
            "args": {
                "branch": {
                    "nargs": "?",
                    "default": None,
                    "help": "the branch of repository.",
                },
                "-i --issue": {"help": "the given issue of the repository."},
                "-c --commit": {"help": "the current commit in the repo website."},
                "-p --print": {
                    "action": "store_true",
                    "help": "only print the url at the terminal, but do not open it.",
                },
                "set_defaults": {"func": _open_func},
            },
        },
    },
}


def _process(args: "argparse.Namespace", extra_unknown: Optional[List] = None) -> None:
    if args.report:
        console.echo(introduce())

    elif args.create_config:
        return CONFIG.create_config_template()

    elif args.config:
        console.echo(GitConfig(format_type=CONFIG.git_config_format).generate())

    elif args.information:
        console.echo(git.get_repo_desc(include_part=CONFIG.repo_info_include))

    elif args.complete:
        from copy import deepcopy

        # Generate competion vars dict.
        completion_vars = deepcopy(argparse_dict)
        completion_vars["args"]["cmd"]["args"].update(
            {k: {"help": v["help"], "args": {}} for k, v in Git_Cmds.items()}
        )

        from .shellcompletion import shell_complete

        shell_complete(get_current_shell(), None, completion_vars, PIGIT_HOME)
        return None

    elif args.ignore_type:
        repo_path, repo_conf_path = git.get_repo_info()

        return GitignoreGenetor(timeout=CONFIG.gitignore_generator_timeout,).launch(
            args.ignore_type,
            dir_path=repo_path,
        )

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

    elif "func" in args:
        kwargs = getattr(args, "kwargs", {})
        args.func(args, extra_unknown, kwargs)

    # Don't have invalid command list.
    # if not list(filter(lambda x: x, vars(known_args).values())):
    else:
        from .interaction import tui_main

        if IS_FIRST_RUN:
            introduce()
            if not confirm("Input `enter` to continue:"):
                return

        tui_main(help_wait=CONFIG.tui_help_showtime)


def process(args: "argparse.Namespace", unknown: List):
    try:
        _process(args, unknown)
    except (KeyboardInterrupt, EOFError):
        raise SystemExit(0) from None


##############
# main entry.
##############
@time_it
def main(custom_commands: Optional[List] = None):
    parser = Parser(argparse_dict)

    # Parse custom comand or parse input command.
    stdargs, extra_unknown = parser.parse(custom_commands)

    # Setup log handle.
    log_file = LOG_FILE_PATH if stdargs.out_log or CONFIG.log_output else None
    setup_logging(debug=stdargs.debug or CONFIG.debug_open, log_file=log_file)

    # Process result.
    process(stdargs, extra_unknown)


if __name__ == "__main__":
    main()
