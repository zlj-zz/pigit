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
from typing import Optional, Union

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
    output_git_local_config,
    output_repository_info,
)
from .repo_utils import (
    add_repos,
    rm_repos,
    rename_repo,
    ll_repos,
    repo_options,
    process_repo_option,
)
from .decorator import time_it
from .config import Config
from .gitignore import GitignoreGenetor
from .shellcompletion import shell_compele, process_argparse
from .processor import CmdProcessor, Git_Cmds, CommandType, get_extra_cmds


Log = logging.getLogger(__name__)


#####################################################################
# Configuration.                                                    #
#####################################################################
CONFIG = Config(
    path=CONFIG_FILE_PATH, version=__version__, auto_load=True
).output_warnings()


#####################################################################
# Implementation of additional functions.                           #
#####################################################################
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


def print_alias(alias_name: str, cmd: str = ""):
    alias = f'alias {alias_name}="pigit {cmd}"'
    print(alias)


def shell_mode(git_processor: CmdProcessor):
    import pigit.tomato

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

        elif command == "tomato":
            # Tomato clock.
            pigit.tomato.main(input_argv_str.split())

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

            elif "tomato" in args_str:
                pigit.tomato.help("tomato")

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


class Parser(object):
    def __init__(self) -> None:
        super(Parser, self).__init__()
        self._parser = argparse.ArgumentParser(
            prog="pigit",
            prefix_chars="-",
            description="Pigit TUI is called automatically if no parameters are followed."
            # formatter_class=CustomHelpFormatter,
        )
        self._subparsers = self._parser.add_subparsers()

        self._add_cmd_args()
        self._add_repo_args()
        self._add_args()

    def _add_cmd_args(self) -> None:
        cmd = self._subparsers.add_parser(
            "cmd",
            help="git short command.",
            description="If you want to use some original git commands, "
            "please use -- to indicate.",
        )
        cmd.add_argument(
            "command",
            nargs="?",
            type=str,
            default=None,
            help="Short git command or other.",
        )
        cmd.add_argument("args", nargs="*", type=str, help="Command parameter list.")
        cmd.add_argument(
            "-s",
            "--show-commands",
            action="store_true",
            help="List all available short command and wealth and exit.",
        )
        cmd.add_argument(
            "-p",
            "--show-part-command",
            type=str,
            metavar="TYPE",
            dest="command_type",
            help="According to given type [%s] list available short command and "
            "wealth and exit." % ", ".join(CommandType.__members__.keys()),
        )
        cmd.add_argument(
            "-t",
            "--types",
            action="store_true",
            help="List all command types and exit.",
        )
        cmd.add_argument(
            "--shell",
            action="store_true",
            help="Go to the pigit shell mode.",
        )
        cmd.set_defaults(func=self._cmd_func)

    def _cmd_func(self, args: argparse.Namespace, unknown: list, kwargs: dict):
        extra_cmd = {
            "shell": {
                "command": lambda _: shell_mode(git_processor),
                "type": "func",
                "help": "Into PIGIT shell mode.",
            },  # only for tips.
        }
        extra_cmd.update(get_extra_cmds())

        git_processor = CmdProcessor(
            extra_cmds=extra_cmd,
            command_prompt=CONFIG.gitprocessor_use_recommend,
            show_original=CONFIG.gitprocessor_show_original,
            use_color=CONFIG.gitprocessor_interactive_color,
            help_wait=CONFIG.gitprocessor_interactive_help_showtime,
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

    def _add_repo_args(self) -> None:

        repo = self._subparsers.add_parser("repo", help="repo options.")
        repo_sub = repo.add_subparsers()

        add = repo_sub.add_parser("add", help="add repo(s).")
        add.add_argument("paths", nargs="+", help="path of reps(s).")
        add.add_argument("--dry-run", action="store_true", help="dry run.")
        add.set_defaults(func=self._repo_func, kwargs={"option": "add"})

        rm = repo_sub.add_parser("rm", help="remove repo(s).")
        rm.add_argument("repos", nargs="+", help="name or path of repo(s).")
        rm.add_argument(
            "--use-path",
            action="store_true",
            help="remove follow path, defult is name.",
        )
        rm.set_defaults(func=self._repo_func, kwargs={"option": "rm"})

        rename = repo_sub.add_parser("rename", help="rename a repo.")
        rename.add_argument("repo", help="the name of repo.")
        rename.add_argument("new_name", help="the new name of repo.")
        rename.set_defaults(func=self._repo_func, kwargs={"option": "rename"})

        ll = repo_sub.add_parser("ll", help="display summary of all repos.")
        ll.add_argument("--simple", action="store_true", help="display simple summary.")
        ll.set_defaults(func=self._repo_func, kwargs={"option": "ll"})

        for name, op in repo_options.items():
            help_msg = op.get("help", "") + " for repo(s)."
            sp = repo_sub.add_parser(name, help=help_msg)
            sp.add_argument("repos", nargs="*", help="name of repo(s).")
            sp.set_defaults(func=self._repo_func, kwargs={"option": name})

    def _repo_func(self, args: argparse.Namespace, unknown: list, kwargs: dict):
        option = kwargs.get("option", "")

        if option == "add":
            add_repos(args.paths, args.dry_run)
        elif option == "rm":
            rm_repos(args.repos, args.use_path)
        elif option == "rename":
            rename_repo(args.repo, args.new_name)
        elif option == "ll":
            ll_repos(args.simple)
        else:
            process_repo_option(args.repos, option)

    def _add_args(self) -> None:
        p = self._parser

        p.add_argument(
            "-v",
            "--version",
            action="version",
            help="Show version and exit.",
            version="Version: %s" % __version__,
        )
        p.add_argument(
            "-r",
            "--report",
            action="store_true",
            help="Report the pigit desc and exit.",
        )
        p.add_argument(
            "-f",
            "--config",
            action="store_true",
            help="Display the config of current git repository and exit.",
        )
        p.add_argument(
            "-i",
            "--information",
            action="store_true",
            help="Show some information about the current git repository.",
        )
        p.add_argument(
            "-d",
            "--debug",
            action="store_true",
            help="Current runtime in debug mode.",
        )
        p.add_argument(
            "--out-log",
            action="store_true",
            help="Print log to console.",
        )

        tool_group = p.add_argument_group(
            title="tools arguments",
            description="Auxiliary type commands.",
        )
        tool_group.add_argument(
            "--alias",
            nargs="*",
            help="print PIGIT alias handle, custom alias name.",
        )
        tool_group.add_argument(
            "-c",
            "--count",
            nargs="?",
            const=".",
            type=str,
            metavar="PATH",
            help="Count the number of codes and output them in tabular form."
            "A given path can be accepted, and the default is the current directory.",
        )
        tool_group.add_argument(
            "-C",
            "--complete",
            action="store_true",
            help="Add shell prompt script and exit.(Supported bash, zsh, fish)",
        )
        tool_group.add_argument(
            "--create-ignore",
            type=str,
            metavar="TYPE",
            dest="ignore_type",
            help="Create a demo .gitignore file. Need one argument, support: [%s]"
            % ", ".join(GitignoreGenetor.Supported_Types.keys()),
        )
        tool_group.add_argument(
            "--create-config",
            action="store_true",
            help="Create a pre-configured file of PIGIT."
            "(If a profile exists, the values available in it are used)",
        )

    def parse(
        self, custom_commands: Union[list, str, None] = None
    ) -> tuple[argparse.Namespace, list]:
        if custom_commands:
            if isinstance(custom_commands, list):
                args, unknown = self._parser.parse_known_args(custom_commands)
            elif isinstance(custom_commands, str):
                args, unknown = self._parser.parse_known_args(custom_commands.split())
            else:
                raise AttributeError("custom_commands need be list or str.")
        else:
            args, unknown = self._parser.parse_known_args()

        Log.debug("Parser result: {0}, {1}".format(args, unknown))
        return args, unknown

    def _process(self, known_args, extra_unknown: Optional[list] = None) -> None:
        if known_args.report:
            introduce()

        elif known_args.config:
            output_git_local_config(CONFIG.git_config_format)

        elif known_args.information:
            output_repository_info(
                show_path=CONFIG.repository_show_path,
                show_remote=CONFIG.repository_show_remote,
                show_branches=CONFIG.repository_show_branchs,
                show_lastest_log=CONFIG.repository_show_lastest_log,
                show_summary=CONFIG.repository_show_summary,
            )

        elif known_args.alias:
            alias = known_args.alias
            if len(alias) > 2:
                return print("error: argument --alias: max support 2 arguments.")
            elif len(alias) == 2:
                return print_alias(alias[0], alias[1])
            else:
                return print_alias(alias[0])

        elif known_args.complete:
            # Generate competion vars dict.
            completion_vars = {
                key: value.get("help", "") for key, value in Git_Cmds.items()
            }

            # Update var dict with shell command.
            completion_vars.update(process_argparse(self._parser))

            shell_compele(get_current_shell(), __project__, completion_vars, PIGIT_HOME)
            return None

        elif known_args.create_config:
            return CONFIG.create_config_template()

        elif known_args.ignore_type:
            repo_path, repo_conf_path = get_repo_info()

            return GitignoreGenetor(timeout=CONFIG.gitignore_generator_timeout,).launch(
                known_args.ignore_type,
                dir_path=repo_path,
            )

        elif known_args.count:
            from .codecounter import CodeCounter

            path = (
                os.path.abspath(known_args.count)
                if known_args.count != "."
                else os.getcwd()
            )
            CodeCounter(
                count_path=path,
                use_ignore=CONFIG.codecounter_use_gitignore,
                result_saved_path=COUNTER_DIR_PATH,
                result_format=CONFIG.codecounter_result_format,
                use_icon=CONFIG.codecounter_show_icon,
            ).count_and_format_print(
                show_invalid=CONFIG.codecounter_show_invalid,
            )
            return None

        elif "func" in known_args:
            kwargs = getattr(known_args, "kwargs", {})
            known_args.func(known_args, extra_unknown, kwargs)

        # Don't have invalid command list.
        # if not list(filter(lambda x: x, vars(known_args).values())):
        else:
            from .interaction import main as interactive_interface

            if IS_FIRST_RUN:
                introduce()
                if not confirm("Input `enter` to continue:"):
                    return

            interactive_interface()

    def process(self, a, b):
        try:
            self._process(a, b)
        except (KeyboardInterrupt, EOFError):
            raise SystemExit(0)


@time_it
def main(custom_commands: Optional[list] = None):
    parser = Parser()

    # Parse custom comand or parse input command.
    if custom_commands is not None:
        stdargs, extra_unknown = parser.parse(custom_commands)
    stdargs, extra_unknown = parser.parse()

    # Setup log handle.
    log_file = LOG_FILE_PATH if stdargs.out_log or CONFIG.stream_output_log else None
    setup_logging(debug=stdargs.debug or CONFIG.debug_mode, log_file=log_file)

    # Process result.
    parser.process(stdargs, extra_unknown)


if __name__ == "__main__":
    main()
