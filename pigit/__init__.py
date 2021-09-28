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
__version__ = "1.3.1"
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
import textwrap
from distutils.util import strtobool
from shutil import get_terminal_size
from typing import Optional

from .log import LogHandle
from .utils import confirm, color_print, is_color
from .common import Color, Fx, TermColor
from .git_utils import (
    Git_Version,
    REPOSITORY_PATH,
    output_repository_info,
    output_git_local_config,
)
from .decorator import time_it
from .codecounter import CodeCounter
from .shell_completion import ShellCompletion, process_argparse
from .gitignore import GitignoreGenetor
from .command_processor import GitProcessor, Git_Cmds, CommandType


Log = logging.getLogger(__name__)

#####################################################################
# Part of compatibility.                                            #
# Handled the incompatibility between python2 and python3.          #
#####################################################################

# For windows.
IS_WIN: bool = sys.platform.lower().startswith("win")
Log.debug("Runtime platform is windows: {0}".format(IS_WIN))
if IS_WIN:
    USER_HOME = os.environ["USERPROFILE"]
    PIGIT_HOME = os.path.join(USER_HOME, __project__)
else:
    USER_HOME = os.environ["HOME"]
    PIGIT_HOME = os.path.join(USER_HOME, ".config", __project__)

LOG_PATH = PIGIT_HOME + "/log/{0}.log".format(__project__)
COUNTER_PATH = PIGIT_HOME + "/Counter"


#####################################################################
# Configuration.                                                    #
#####################################################################
class ConfigError(Exception):
    """Config error. Using by `Config`."""

    pass


class Config(object):
    """PIGIT configuration class."""

    _conf_path: str = PIGIT_HOME + "/pigit.conf"  # default config path.

    CONFIG_TEMPLATE: str = textwrap.dedent(
        """\
        #? Config file for pigit v. {version}

        #  ____ ___ ____ ___ _____                            __ _
        # |  _ \\_ _/ ___|_ _|_   _|           ___ ___  _ __  / _(_) __ _
        # | |_) | | |  _ | |  | |_____ _____ / __/ _ \\| '_ \\| |_| |/ _` |
        # |  __/| | |_| || |  | |_____|_____| (_| (_) | | | |  _| | (_| |
        # |_|  |___\\____|___| |_|            \\___\\___/|_| |_|_| |_|\\__, |
        #                                     {version:>20} |___/
        # Git-tools -- pigit configuration.

        # Show original git command.
        gitprocessor_show_original={gitprocessor_show_original}

        # Is it recommended to correct when entering wrong commands.
        gitprocessor_use_recommend={gitprocessor_use_recommend}

        # Whether color is enabled in interactive mode.
        gitprocessor_interactive_color={gitprocessor_interactive_color}

        # Display time of help information in interactive mode, 0 is permanent.
        gitprocessor_interactive_help_showtime={gitprocessor_interactive_help_showtime}

        # Whether to use the ignore configuration of the `.gitignore` file.
        codecounter_use_gitignore={codecounter_use_gitignore}

        # Whether show files that cannot be counted.
        codecounter_show_invalid={codecounter_show_invalid}

        # Whether show files icons. Font support required, like: 'Nerd Font'
        codecounter_show_icon={codecounter_show_icon}

        # Output format of statistical results.
        # Supported: [table, simple]
        # When the command line width is not enough, the `simple ` format is forced.
        codecounter_result_format={codecounter_result_format}

        # Timeout for getting `.gitignore` template from net.
        gitignore_generator_timeout={gitignore_generator_timeout}

        # Git local config print format.
        # Supported: [table, normal]
        git_config_format={git_config_format}

        # Control which parts need to be displayed when viewing git repository information.
        repository_show_path={repository_show_path}
        repository_show_remote={repository_show_remote}
        repository_show_branchs={repository_show_branchs}
        repository_show_lastest_log={repository_show_lastest_log}
        repository_show_summary={repository_show_summary}

        # Whether with color when use `-h` get help message.
        help_use_color={help_use_color}

        # The max line width when use `-h` get help message.
        help_max_line_width={help_max_line_width}

        # Whether run PIGIT in debug mode.
        debug_mode={debug_mode}

        """
    )

    # yapf: disable
    _keys :list[str]= [
        'gitprocessor_show_original', 'gitprocessor_use_recommend',
        'gitprocessor_interactive_color', 'gitprocessor_interactive_help_showtime',
        'codecounter_use_gitignore', 'codecounter_show_invalid',
        'codecounter_result_format', 'codecounter_show_icon',
        'gitignore_generator_timeout',
        'git_config_format',
        'repository_show_path', 'repository_show_remote', 'repository_show_branchs',
        'repository_show_lastest_log', 'repository_show_summary',
        'help_use_color', 'help_max_line_width',
        'debug_mode'
    ]
    # yapf: enable

    # config default values.
    gitprocessor_show_original: bool = True
    gitprocessor_use_recommend: bool = True
    gitprocessor_interactive_color: bool = True
    gitprocessor_interactive_help_showtime: float = 1.5

    codecounter_use_gitignore: bool = True
    codecounter_show_invalid: bool = False
    codecounter_show_icon: bool = False
    codecounter_result_format: str = "table"  # table, simple
    _supported_result_format: list = ["table", "simple"]

    gitignore_generator_timeout: int = 60

    git_config_format: str = "table"
    _supported_git_config_format: list = ["normal", "table"]

    repository_show_path: bool = True
    repository_show_remote: bool = True
    repository_show_branchs: bool = True
    repository_show_lastest_log: bool = True
    repository_show_summary: bool = False

    help_use_color: bool = True
    help_max_line_width: int = 90

    debug_mode: bool = False

    # Store warning messages.
    warnings: list = []

    def __init__(self, path: Optional[str] = None) -> None:
        super(Config, self).__init__()
        if not path:
            self.config_path = self._conf_path
        else:
            self.config_path = path
        conf = self.load_config()

        for key in self._keys:
            if key in conf.keys() and conf[key] != "==error==":
                setattr(self, key, conf[key])

    def load_config(self) -> dict:
        new_config = {}
        config_file = self.config_path
        try:
            with open(config_file) as cf:
                for line in cf:
                    line = line.strip()
                    if line.startswith("#? Config"):
                        new_config["version"] = line[line.find("v. ") + 3 :]
                        continue
                    if line.startswith("#"):
                        # comment line.
                        continue
                    if "=" not in line:
                        # invalid line.
                        continue
                    key, line = line.split("=", maxsplit=1)

                    # processing.
                    key = key.strip()
                    line = line.strip().strip('"')

                    # checking.
                    if key not in self._keys:
                        self.warnings.append("'{0}' is not be supported!".format(key))
                        continue
                    elif type(getattr(self, key)) == int:
                        try:
                            new_config[key] = int(line)
                        except ValueError:
                            self.warnings.append(
                                'Config key "{0}" should be an integer!'.format(key)
                            )
                    elif type(getattr(self, key)) == bool:
                        try:
                            # True values are y, yes, t, true, on and 1;
                            # false values are n, no, f, false, off and 0.
                            # Raises ValueError if val is anything else.
                            new_config[key] = bool(strtobool(line))
                        except ValueError:
                            self.warnings.append(
                                'Config key "{0}" can only be True or False!'.format(
                                    key
                                )
                            )
                    elif type(getattr(self, key)) == str:
                        if "color" in key and not is_color(line):
                            self.warnings.append(
                                'Config key "{0}" should be RGB string, like: #FF0000'.format(
                                    key
                                )
                            )
                            continue
                        new_config[key] = str(line)
        except Exception as e:
            Log.error(str(e) + str(e.__traceback__))

        if (  # check codecounter output format whether supported.
            "codecounter_result_format" in new_config
            and new_config["codecounter_result_format"]
            not in self._supported_result_format
        ):
            new_config["codecounter_result_format"] = "==error=="
            self.warnings.append(
                'Config key "{0}" support must in {1}'.format(
                    "codecounter_result_format", self._supported_result_format
                )
            )

        if (
            "git_config_format" in new_config
            and new_config["git_config_format"] not in self._supported_git_config_format
        ):
            new_config["git_config_format"] = "==error=="
            self.warnings.append(
                'Config key "{0}" support must in {1}'.format(
                    "git_config_format", self._supported_git_config_format
                )
            )

        if "version" in new_config and not (
            # If current version is a [beta] verstion then will not tip.
            # Else if version is not right will tip.
            new_config["version"] == __version__
            or "beta" in __version__
            or "alpha" in __version__
        ):
            print(new_config["version"])
            self.warnings.append(
                "The current configuration file is not up-to-date."
                "You'd better recreate it."
            )

        return new_config

    def create_config_template(self) -> None:
        if not os.path.isdir(PIGIT_HOME):
            os.makedirs(PIGIT_HOME, exist_ok=True)

        if os.path.exists(self.config_path) and not confirm(
            "Configuration exists, overwrite? [y/n]"
        ):
            return None

        # Try to load already has config.
        conf = self.load_config()
        for key in self._keys:
            if not conf.get(key, None) or conf[key] == "==error==":
                conf[key] = getattr(self, key)
        conf["version"] = __version__

        # Write config. Will save before custom setting.
        try:
            with open(
                self.config_path, "w" if os.path.isfile(self.config_path) else "x"
            ) as f:
                f.write(self.CONFIG_TEMPLATE.format(**conf))
        except Exception as e:
            Log.error(str(e) + str(e.__traceback__))
            print("Failed, create config.")
        else:
            print("Successful.")


CONFIG = Config()
if CONFIG.warnings:
    for warning in CONFIG.warnings:
        print(warning)
    CONFIG.warnings = []


#####################################################################
# Implementation of additional functions.                           #
#####################################################################
def introduce() -> None:
    """Print the description information."""

    # Print tools version and path.
    color_print("[%s] version: %s" % (__project__, __version__), Fx.b)

    # Print git version.
    if Git_Version is None:
        print("Don't found Git, maybe need install.")
    else:
        print(Git_Version)

    # Print package path.
    color_print("Path: ", Fx.b, end="")
    color_print("%s\n" % __file__, TermColor.SkyBlue, Fx.underline)

    # Print description.
    color_print("Description:", Fx.b)
    color_print(
        (
            "  Terminal tool, help you use git more simple."
            " Support Linux and MacOS. Partial support for windows.\n"
            "  It use short command to replace the original command, like: \n"
            "  `pigit ws` -> `git status --short`, `pigit b` -> `git branch`.\n"
            "  Also you use `pigit -s` to get the all short command, have fun"
            " and good lucky.\n"
            "  The open source path: %s" % (TermColor.SkyBlue + Fx.underline + __url__)
        ),
        Fx.italic,
    )

    print("\nYou can use ", end="")
    color_print("-h", TermColor.Green, end="")
    print(" or ", end="")
    color_print("--help", TermColor.Green, end="")
    print(" to get help and more usage.\n")


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
                extra_cmds = extra_cmd.extra_cmds
            except AttributeError:
                Log.error("Can't found dict name is 'extra_cmds'.")

    # print(extra_cmds)
    return extra_cmds


class CustomHelpFormatter(argparse.HelpFormatter):
    """Formatter for generating usage messages and argument help strings.

    This class inherits `argparse.HelpFormatter` and rewrites some methods
    to complete customization.
    """

    def __init__(
        self, prog, indent_increment=2, max_help_position=24, width=90, colors=[]
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
            description="If you want to use some original git commands, please use -- to indicate.",
            prefix_chars="-",
            formatter_class=CustomHelpFormatter,
        )
        self._add_arguments()

    def _add_arguments(self) -> None:
        self._parser.add_argument(
            "-s",
            "--show-commands",
            action="store_true",
            help="List all available short command and wealth and exit.",
        )
        self._parser.add_argument(
            "-S",
            "--show-command",
            type=str,
            metavar="TYPE",
            dest="command_type",
            help="According to given type(%s) list available short command and wealth and exit."
            % ", ".join(CommandType.__members__.keys()),
        )
        self._parser.add_argument(
            "-t",
            "--types",
            action="store_true",
            help="List all command types and exit.",
        )
        self._parser.add_argument(
            "-f",
            "--config",
            action="store_true",
            help="Display the config of current git repository and exit.",
        )
        self._parser.add_argument(
            "-i",
            "--information",
            action="store_true",
            help="Show some information about the current git repository.",
        )
        self._parser.add_argument(
            "-c",
            "--count",
            nargs="?",
            const=".",
            type=str,
            metavar="PATH",
            help="Count the number of codes and output them in tabular form."
            "A given path can be accepted, and the default is the current directory.",
        )
        self._parser.add_argument(
            "-C",
            "--complete",
            action="store_true",
            help="Add shell prompt script and exit.(Supported `bash`, `zsh`, `fish`)",
        )
        self._parser.add_argument(
            "--create-ignore",
            type=str,
            metavar="TYPE",
            dest="ignore_type",
            help="Create a demo `.gitignore` file. Need one argument, support: [%s]"
            % ", ".join(GitignoreGenetor.Supported_Types.keys()),
        )
        self._parser.add_argument(
            "--create-config",
            action="store_true",
            help="Create a preconfigured file of PIGIT."
            "(If a profile exists, the values available in it are used)",
        )
        self._parser.add_argument(
            "--shell",
            action="store_true",
            help="Go to the pigit shell mode.",
        )
        self._parser.add_argument(
            "--debug",
            action="store_true",
            help="Current runtime in debug mode.",
        )
        self._parser.add_argument(
            "--out-log",
            action="store_true",
            help="Print log to console.",
        )
        self._parser.add_argument(
            "-v",
            "--version",
            action="version",
            help="Show version and exit.",
            version="Version: %s" % __version__,
        )
        self._parser.add_argument(
            "command", nargs="?", type=str, help="Short git command."
        )
        self._parser.add_argument(
            "args", nargs="*", type=str, help="Command parameter list."
        )

    def parse(self, custom_commands: Optional[list] = None):
        if custom_commands:
            return self._parser.parse_known_args(custom_commands)
        return self._parser.parse_known_args()

    def process(self, known_args, extra_unknown: Optional[list] = None) -> None:
        try:
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

            git_processor = GitProcessor(
                extra_cmds=get_extra_cmds(),
                use_recommend=CONFIG.gitprocessor_use_recommend,
                show_original=CONFIG.gitprocessor_show_original,
                use_color=CONFIG.gitprocessor_interactive_color,
                help_wait=CONFIG.gitprocessor_interactive_help_showtime,
            )

            def _shell_mode():
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

            if known_args.shell:
                _shell_mode()

            if known_args.show_commands:
                return git_processor.command_help()

            if known_args.command_type:
                return git_processor.command_help_by_type(known_args.command_type)

            if known_args.types:
                return git_processor.type_help()

            if known_args.command:
                if known_args.command == "shell":
                    return _shell_mode()
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

    # parse custom comand, if has.
    if custom_commands is not None:
        stdargs = parser.parse(custom_commands)
    stdargs, extra_unknown = parser.parse()
    # print(stdargs, extra_unknown)

    # Setup log handle.
    LogHandle.setup_logging(
        debug=stdargs.debug or CONFIG.debug_mode,
        log_file=None if stdargs.out_log else LOG_PATH,
    )

    # process result.
    parser.process(stdargs, extra_unknown)


if __name__ == "__main__":
    main()
