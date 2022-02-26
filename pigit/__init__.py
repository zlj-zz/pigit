# -*- coding:utf-8 -*-

# MIT License
#
# Copyright (c) 2021 Zachary
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.


import os
import argparse
import logging
from typing import Optional

from .log import setup_logging
from .const import (
    __version__,
    __url__,
    __project__,
    PIGIT_HOME,
    LOG_FILE_PATH,
    CONFIG_FILE_PATH,
    COUNTER_DIR_PATH,
    IS_FIRST_RUN,
)
from .common import render_str, get_current_shell, confirm
from .git_utils import (
    get_git_version,
    get_repo_info,
    get_branches,
    get_remote,
    output_git_local_config,
    output_repository_info,
)
from .repo_utils import (
    add_repos,
    clear_repos,
    rm_repos,
    rename_repo,
    ll_repos,
    repo_options,
    process_repo_option,
)
from .decorator import time_it
from .config import Config
from .argparse_utils import Parser
from .gitignore import GitignoreGenetor
from .shellcompletion import shell_compele
from .processor import CmdProcessor, Git_Cmds, CommandType, get_extra_cmds


Log = logging.getLogger(__name__)


#################
# Configuration.
#################
CONFIG = Config(
    path=CONFIG_FILE_PATH, version=__version__, auto_load=True
).output_warnings()


##########################################
# Implementation of additional functions.
##########################################
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
        print(render_str("`Don't found Git, maybe need install.`<error>"))
    else:
        print(git_version)

    # Print package path.
    print(
        render_str(
            "b`Local path`: u`{}`<sky_blue>\n".format(
                os.path.dirname(__file__.replace("./", ""))
            )
        )
    )

    # Print description.
    print(
        render_str(
            "b`Description:`\n"
            "  Terminal tool, help you use git more simple. Support Linux, MacOS and Windows.\n"
            f"  The open source path on github: u`{__url__}`<sky_blue>\n\n"
            "You can use `-h`<ok> or `--help`<ok> to get help and usage."
        )
    )


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


def _cmd_func(args: argparse.Namespace, unknown: list, kwargs: dict):
    # If you want to manipulate the current folder with git,
    # try adding it to repos automatically.
    if CONFIG.repo_auto_append:
        repo_path, repo_conf = get_repo_info()
        add_repos([repo_path], silent=True)

    extra_cmd: dict = {
        "shell": {
            "command": lambda _: shell_mode(git_processor),
            "type": "func",
            "help": "Into PIGIT shell mode.",
        },  # only for tips.
    }
    extra_cmd.update(get_extra_cmds())

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
        print(render_str("`pigit cmd -h`<ok> for help."))


def _repo_func(args: argparse.Namespace, unknown: list, kwargs: dict):
    option: str = kwargs.get("option", "")

    if option == "add":
        add_repos(args.paths, args.dry_run)
    elif option == "rm":
        rm_repos(args.repos, args.use_path)
    elif option == "rename":
        rename_repo(args.repo, args.new_name)
    elif option == "ll":
        ll_repos(args.simple)
    elif option == "clear":
        clear_repos()
    else:
        process_repo_option(args.repos, option)


def _open_func(args: argparse.Namespace, unknown: list, kwargs: dict):
    branch = issue = commit = ""

    remote_url = get_remote()

    if args.branch:
        branches = get_branches()
        branch = f"/tree/{args.branch}"
        remote_url += branch
    elif args.issue:
        issue = f"/issues/{args.issue}"
        remote_url += issue
    elif args.commit:
        commit = f"/commit/{args.commit}"
        remote_url += commit

    if args.print:
        print(render_str(f"Remote URL: `{remote_url}`<sky_blue>"))
    else:
        import webbrowser

        webbrowser.open(remote_url)


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
                        "help": "Create a demo .gitignore file. Need one argument, support: [%s]"
                        % ", ".join(GitignoreGenetor.Supported_Types.keys()),
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
                "args": {"nargs": "*", "type": str, "help": "Command parameter list."},
                "-s --show-commands": {
                    "action": "store_true",
                    "help": "List all available short command and wealth and exit.",
                },
                "-p --show-part-command": {
                    "type": str,
                    "metavar": "TYPE",
                    "dest": "command_type",
                    "help": "According to given type [%s] list available short command and wealth and exit."
                    % ", ".join(CommandType.__members__.keys()),
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
                        "--dry-run": {"action": "store_true", "help": "dry run."},
                        "set_defaults": {
                            "func": _repo_func,
                            "kwargs": {"option": "add"},
                        },
                    },
                },
                "rm": {
                    "help": "remove repo(s).",
                    "args": {
                        "repos": {"nargs": "+", "help": "name or path of repo(s)."},
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
                            "repos": {"nargs": "*", "help": "name of repo(s)."},
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


def _process(args: argparse.Namespace, extra_unknown: Optional[list] = None) -> None:
    if args.report:
        introduce()

    elif args.create_config:
        return CONFIG.create_config_template()

    elif args.config:
        output_git_local_config(CONFIG.git_config_format)

    elif args.information:
        output_repository_info(include_part=CONFIG.repo_info_include)

    elif args.complete:
        from copy import deepcopy

        # Generate competion vars dict.
        completion_vars = deepcopy(argparse_dict)
        completion_vars["args"]["cmd"]["args"].update(
            {k: {"help": v["help"], "args": {}} for k, v in Git_Cmds.items()}
        )

        shell_compele(get_current_shell(), None, completion_vars, PIGIT_HOME)
        return None

    elif args.ignore_type:
        repo_path, repo_conf_path = get_repo_info()

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
            result_format=CONFIG.counter_format,
            use_icon=CONFIG.counter_show_icon,
        ).count_and_format_print(
            show_invalid=CONFIG.counter_show_invalid,
        )
        return None

    elif "func" in args:
        kwargs = getattr(args, "kwargs", {})
        args.func(args, extra_unknown, kwargs)

    # Don't have invalid command list.
    # if not list(filter(lambda x: x, vars(known_args).values())):
    else:
        from .interaction import main as interactive_interface

        if IS_FIRST_RUN:
            introduce()
            if not confirm("Input `enter` to continue:"):
                return

        interactive_interface(help_wait=CONFIG.tui_help_showtime)


def process(args: argparse.Namespace, unknown: list):
    try:
        _process(args, unknown)
    except (KeyboardInterrupt, EOFError):
        raise SystemExit(0)


#############
# main entry
#############
@time_it
def main(custom_commands: Optional[list] = None):
    parser = Parser(argparse_dict)

    # Parse custom comand or parse input command.
    stdargs, extra_unknown = parser.parse()

    # Setup log handle.
    log_file = LOG_FILE_PATH if stdargs.out_log or CONFIG.log_output else None
    setup_logging(debug=stdargs.debug or CONFIG.debug_open, log_file=log_file)

    # Process result.
    process(stdargs, extra_unknown)


if __name__ == "__main__":
    main()
