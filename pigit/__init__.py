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


__project__ = "pigit"
__version__ = "1.3.2"
__url__ = "https://github.com/zlj-zz/pigit.git"
__uri__ = __url__

__author__ = "Zachary Zhang"
__email__ = "zlj19971222@outlook.com"

__license__ = "MIT"
__copyright__ = "Copyright (c) 2021 Zachary"


import os
import sys
import argparse
import logging
from shutil import get_terminal_size
from typing import Optional, Union

from .log import LogHandle
from .common import Color, Fx, TermColor, color_print
from .gitinfo import (
    Git_Version,
    REPOSITORY_PATH,
    output_repository_info,
    output_git_local_config,
)
from .decorator import time_it
from .config import Config
from .codecounter import CodeCounter
from .shell_completion import ShellCompletion, process_argparse
from .gitignore import GitignoreGenetor
from .interaction import InteractiveStatus, InteractiveCommit
from .processor import CmdProcessor, Git_Cmds, CommandType


Log = logging.getLogger(__name__)

#####################################################################
# Part of compatibility.                                            #
# Handled the incompatibility between python2 and python3.          #
#####################################################################

# For windows.
USER_HOME: str = ""
PIGIT_HOME: str = ""
IS_WIN: bool = sys.platform.lower().startswith("win")
Log.debug("Runtime platform is windows: {0}".format(IS_WIN))

if IS_WIN:
    USER_HOME = os.environ["USERPROFILE"]
    PIGIT_HOME = os.path.join(USER_HOME, __project__)
else:
    USER_HOME = os.environ["HOME"]
    PIGIT_HOME = os.path.join(USER_HOME, ".config", __project__)

LOG_PATH: str = PIGIT_HOME + "/log/{0}.log".format(__project__)
CONFIG_PATH: str = PIGIT_HOME + "/pigit.conf"
COUNTER_PATH: str = PIGIT_HOME + "/Counter"


#####################################################################
# Configuration.                                                    #
#####################################################################
CONFIG = Config(path=CONFIG_PATH, current_version=__version__)
if CONFIG.warnings:
    for warning in CONFIG.warnings:
        print(warning)
    CONFIG.warnings = []


#####################################################################
# Implementation of additional functions.                           #
#####################################################################
def introduce() -> None:
    """Print the description information."""

    # Print version.
    print(
        """
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
    if Git_Version is None:
        color_print("Don't found Git, maybe need install.", TermColor.Red)
    else:
        print(Git_Version)

    # Print package path.
    color_print("Local path: ", Fx.b, end="")
    f_p = __file__.replace("./", "")  # f_p -> file path
    color_print("%s\n" % f_p, TermColor.SkyBlue, Fx.underline)

    # Print description.
    color_print("Description:", Fx.b)
    color_print(
        "  Terminal tool, help you use git more simple."
        " Support Linux, MacOS and Windows.\n"
        "  It use short command to replace the original command, like: \n"
        "  ``{green}pigit ws{rs}`` -> ``{green}git status --short{rs}``,"
        " ``{green}pigit b{rs}`` -> ``{green}git branch{rs}``.\n"
        "  Also you use ``{green}pigit -s{rs}`` to get the all short command,"
        " have fun and good lucky.\n"
        "  The open source path on github: {url}".format(
            url=TermColor.SkyBlue + Fx.underline + __url__,
            green=TermColor.Green,
            rs=Fx.reset,
        ),
        Fx.italic,
    )

    print(
        "\nYou can use {green}-h{rs} or {green}--help{rs} "
        "to get help and more usage.".format(green=TermColor.Green, rs=Fx.reset)
    )


def get_extra_cmds() -> dict:
    """Get custom cmds.

    Load the `extra_cmds.py` file under PIGIT HOME, check whether `extra_cmds`
    exists, and return it. If not have, return a empty dict.

    Returns:
        (dict[str,str]): extra cmds dict.
    """
    import imp

    extra_cmd_path: str = PIGIT_HOME + "/extra_cmds.py"
    extra_cmds = {}

    if os.path.isfile(extra_cmd_path):
        try:
            extra_cmd = imp.load_source("extra_cmd", extra_cmd_path)
        except Exception as e:
            Log.error(
                "Can't load file '{0}';{1};{2}".format(
                    extra_cmd_path, str(e), str(e.__traceback__)
                )
            )
        else:
            try:
                extra_cmds = extra_cmd.extra_cmds  # type: ignore
            except AttributeError:
                Log.error("Can't found dict name is 'extra_cmds'.")

    # print(extra_cmds)
    return extra_cmds


def shell_mode(git_processor: CmdProcessor):
    import pigit.tomato

    print(
        "Welcome come PIGIT shell.\n"
        "You can use short commands directly. Input '?' to get help.\n"
    )
    while True:
        command = input("(pigit)> ").strip()
        if not command:
            continue

        command_args = command.split()
        head_command = command_args[0]

        if head_command in ["quit", "exit"]:  # ctrl+c
            break
        elif head_command in git_processor.cmds.keys():
            git_processor.process_command(head_command, command_args[1:])
        elif head_command == "tomato":
            # Tomato clock.
            pigit.tomato.main(command_args)
        elif head_command == "?":
            other_ = command_args[1:]
            if not other_:
                git_processor.command_help()
            else:
                print(other_)
                for item in other_:
                    if item in git_processor.cmds.keys():
                        print(git_processor._generate_help_by_key(item))
                    elif item == "tomato":
                        pigit.tomato.help("tomato")
        else:
            os.system(command)
    return None


def interactive_interface(args):
    flag: int = 1

    if args:
        ready_flag = args[0]
        if ready_flag in "0123456789":
            flag = int(ready_flag)

    while flag and flag > 0:
        if flag == 1:
            flag = InteractiveStatus(
                use_color=CONFIG.gitprocessor_interactive_color,
                help_wait=CONFIG.gitprocessor_interactive_help_showtime,
            ).run()
        elif flag == 2:
            flag = InteractiveCommit(
                use_color=CONFIG.gitprocessor_interactive_color,
                help_wait=CONFIG.gitprocessor_interactive_help_showtime,
            ).run()
        else:
            flag = 1


class CustomHelpFormatter(argparse.HelpFormatter):
    """Formatter for generating usage messages and argument help strings.

    This class inherits `argparse.HelpFormatter` and rewrites some methods
    to complete customization.
    """

    def __init__(
        self, prog, indent_increment=2, max_help_position=24, width=90, colors=None
    ):
        width = CONFIG.help_max_line_width
        max_width, _ = get_terminal_size()

        width = width if width < max_width else max_width - 2
        super(CustomHelpFormatter, self).__init__(
            prog, indent_increment, max_help_position, width
        )
        if not colors or not isinstance(colors, list):
            colors = {
                "red": Color.fg("#FF6347"),  # Tomato
                "green": Color.fg("#98FB98"),  # PaleGreen
                "yellow": Color.fg("#EBCB8C"),  # Yellow
                "blue": Color.fg("#87CEFA"),  # SkyBlue
                # Color.fg("#FFC0CB"),  # Pink
            }
        self.colors = colors
        self.color_len = len(colors)
        self._old_color = None

    def _format_action(self, action):
        # determine the required width and the entry label
        help_position = min(self._action_max_length + 2, self._max_help_position)
        help_width = max(self._width - help_position, 11)
        action_width = help_position - self._current_indent - 2
        action_header = self._format_action_invocation(action)

        # no help; start on same line and add a final newline
        if not action.help:
            tup = self._current_indent, "", action_header
            action_header = "%*s%s\n" % tup

        # short action name; start on the same line and pad two spaces
        elif len(action_header) <= action_width:
            tup = self._current_indent, "", action_width, action_header
            action_header = "%*s%-*s  " % tup
            indent_first = 0

        # long action name; start on the next line
        else:
            tup = self._current_indent, "", action_header
            action_header = "%*s%s\n" % tup
            indent_first = help_position

        # collect the pieces of the action help
        # @Overwrite
        if CONFIG.help_use_color:
            _color = self.colors["green"]
        else:
            _color = ""
        parts = [_color + action_header + Fx.reset]

        # if there was help for the action, add lines of help text
        if action.help:
            help_text = self._expand_help(action)
            help_lines = self._split_lines(help_text, help_width)
            parts.append("%*s%s\n" % (indent_first, "", help_lines[0]))
            for line in help_lines[1:]:
                parts.append("%*s%s\n" % (help_position, "", line))

        # or add a newline if the description doesn't end with one
        elif not action_header.endswith("\n"):
            parts.append("\n")

        # if there are any sub-actions, add their help as well
        for subaction in self._iter_indented_subactions(action):
            parts.append(self._format_action(subaction))

        # return a single string
        return self._join_parts(parts)

    def _fill_text(self, text, width, indent):
        try:
            return "".join(indent + line for line in text.splitlines(keepends=True))
        except TypeError:
            return "".join(indent + line for line in text.splitlines())

    def _get_help_string(self, action):
        help = action.help
        if "%(default)" not in action.help:
            if action.default is not argparse.SUPPRESS:
                defaulting_nargs = [argparse.OPTIONAL, argparse.ZERO_OR_MORE]
                if action.option_strings or action.nargs in defaulting_nargs:
                    # help += " (default: %(default)s)"
                    pass
        return help


class Parser(object):
    def __init__(self) -> None:
        super(Parser, self).__init__()
        self._parser = argparse.ArgumentParser(
            prog="pigit",
            description="If you want to use some original git commands, "
            "please use -- to indicate.",
            prefix_chars="-",
            formatter_class=CustomHelpFormatter,
        )
        self._add_arguments()

    def _add_arguments(self) -> None:
        p = self._parser

        p.add_argument(
            "-v",
            "--version",
            action="version",
            help="Show version and exit.",
            version="Version: %s" % __version__,
        )
        p.add_argument(
            "-C",
            "--complete",
            action="store_true",
            help="Add shell prompt script and exit.(Supported `bash`, `zsh`, `fish`)",
        )
        p.add_argument(
            "-s",
            "--show-commands",
            action="store_true",
            help="List all available short command and wealth and exit.",
        )
        p.add_argument(
            "-p",
            "--show-part-command",
            type=str,
            metavar="TYPE",
            dest="command_type",
            help="According to given type [%s] list available short command and "
            "wealth and exit." % ", ".join(CommandType.__members__.keys()),
        )
        p.add_argument(
            "-t",
            "--types",
            action="store_true",
            help="List all command types and exit.",
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
            "-f",
            "--config",
            action="store_true",
            help="Display the config of current git repository and exit.",
        )
        tool_group.add_argument(
            "-i",
            "--information",
            action="store_true",
            help="Show some information about the current git repository.",
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
            "--create-ignore",
            type=str,
            metavar="TYPE",
            dest="ignore_type",
            help="Create a demo `.gitignore` file. Need one argument, support: [%s]"
            % ", ".join(GitignoreGenetor.Supported_Types.keys()),
        )
        p.add_argument(
            "--create-config",
            action="store_true",
            help="Create a preconfigured file of PIGIT."
            "(If a profile exists, the values available in it are used)",
        )
        tool_group.add_argument(
            "--shell",
            action="store_true",
            help="Go to the pigit shell mode.",
        )

        p.add_argument(
            "command", nargs="?", type=str, help="Short git command or other."
        )
        p.add_argument("args", nargs="*", type=str, help="Command parameter list.")

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

    def process(self, known_args, extra_unknown: Optional[list] = None) -> None:
        try:
            if known_args.config:
                output_git_local_config(CONFIG.git_config_format)

            if known_args.information:
                output_repository_info(
                    show_path=CONFIG.repository_show_path,
                    show_remote=CONFIG.repository_show_remote,
                    show_branches=CONFIG.repository_show_branchs,
                    show_lastest_log=CONFIG.repository_show_lastest_log,
                    show_summary=CONFIG.repository_show_summary,
                )

            if known_args.complete:
                # Generate competion vars dict.
                completion_vars = {
                    key: value.get("help", "") for key, value in Git_Cmds.items()
                }

                # Update var dict with shell command.
                completion_vars.update(process_argparse(self._parser))

                ShellCompletion(
                    __project__, completion_vars, PIGIT_HOME
                ).complete_and_use()
                return None

            if known_args.create_config:
                return CONFIG.create_config_template()

            if known_args.ignore_type:
                GitignoreGenetor(timeout=CONFIG.gitignore_generator_timeout,).launch(
                    known_args.ignore_type,
                    dir_path=REPOSITORY_PATH,
                )
                return None

            if known_args.count:
                path = known_args.count if known_args.count != "." else os.getcwd()
                CodeCounter(
                    count_path=path,
                    use_ignore=CONFIG.codecounter_use_gitignore,
                    result_saved_path=COUNTER_PATH,
                    result_format=CONFIG.codecounter_result_format,
                    use_icon=CONFIG.codecounter_show_icon,
                ).count_and_format_print(
                    show_invalid=CONFIG.codecounter_show_invalid,
                )
                return None

            extra_cmd = {
                "ui": {
                    "belong": CommandType.Index,
                    "command": interactive_interface,
                    "help": "interactive operation git tree status.",
                    "type": "func",
                    "has_arguments": True,
                },
                "shell": {
                    "command": "",
                    "help": "Into PIGIT shell mode.",
                },  # only for tips.
            }
            extra_cmd.update(get_extra_cmds())

            git_processor = CmdProcessor(
                extra_cmds=extra_cmd,
                use_recommend=CONFIG.gitprocessor_use_recommend,
                show_original=CONFIG.gitprocessor_show_original,
                use_color=CONFIG.gitprocessor_interactive_color,
                help_wait=CONFIG.gitprocessor_interactive_help_showtime,
            )

            if known_args.shell:
                shell_mode(git_processor)

            if known_args.show_commands:
                return git_processor.command_help()

            if known_args.command_type:
                return git_processor.command_help_by_type(known_args.command_type)

            if known_args.types:
                return git_processor.type_help()

            if known_args.command:
                if known_args.command == "shell":
                    return shell_mode(git_processor)
                else:
                    command = known_args.command
                    known_args.args.extend(extra_unknown)  # type: list
                    git_processor.process_command(command, known_args.args)
                    return None

            # Don't have invalid command list.
            if not list(filter(lambda x: x, vars(known_args).values())):
                introduce()
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
    log_file = LOG_PATH if stdargs.out_log or CONFIG.stream_output_log else None
    LogHandle.setup_logging(debug=stdargs.debug or CONFIG.debug_mode, log_file=log_file)

    # Process result.
    parser.process(stdargs, extra_unknown)


if __name__ == "__main__":
    main()
