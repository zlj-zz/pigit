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

from __future__ import print_function, division, absolute_import


__project__ = "pigit"
__version__ = "1.0.8"
__url__ = "https://github.com/zlj-zz/pigit.git"
__uri__ = __url__

__author__ = "Zachary Zhang"
__email__ = "zlj19971222@outlook.com"

__license__ = "MIT"
__copyright__ = "Copyright (c) 2021 Zachary"


import os
import sys
import signal
import argparse
import logging
import logging.handlers
import textwrap
from distutils.util import strtobool

from .log import LogHandle
from .compat import get_terminal_size
from .utils import confirm, color_print, leave
from .common import Color, Fx, TermColor
from .git_utils import Git_Version, Repository_Path, repository_info, git_local_config
from .decorator import time_it
from .codecounter import CodeCounter
from .shell_completion import ShellCompletion, process_argparse
from .gitignore import GitignoreGenetor
from .command_processor import GitProcessor, Git_Cmds


Log = logging.getLogger(__name__)

#####################################################################
# Part of compatibility.                                            #
# Handled the incompatibility between python2 and python3.          #
#####################################################################

# For windows.
IS_WIN = sys.platform.lower().startswith("win")
if IS_WIN:
    USER_HOME = os.environ["USERPROFILE"]
    PIGIT_HOME = os.path.join(USER_HOME, __project__)
else:
    USER_HOME = os.environ["HOME"]
    PIGIT_HOME = os.path.join(USER_HOME, ".config", __project__)

LOG_PATH = PIGIT_HOME + "/log/{}.log".format(__project__)
COUNTER_PATH = PIGIT_HOME + "/Counter"


class ConfigError(Exception):
    """Config error. Using by `Config`."""

    pass


class Config(object):
    Conf_Path = PIGIT_HOME + "/pigit.conf"
    Config_Template = textwrap.dedent(
        """
        #? Config file for pigit v. {version}
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

        # Wether show files that cannot be counted.
        codecounter_show_invalid={codecounter_show_invalid}

        # Output format of statistical results.
        # Supported: [table, simple]
        # When the command line width is not enough, the `simple ` format is forced.
        codecounter_result_format={codecounter_result_format}


        # Timeout for getting `.gitignore` template from net.
        gitignore_generator_timeout={gitignore_generator_timeout}


        # Control which parts need to be displayed when viewing git repository information.
        repository_show_path={repository_show_path}
        repository_show_remote={repository_show_remote}
        repository_show_branchs={repository_show_branchs}
        repository_show_lastest_log={repository_show_lastest_log}
        repository_show_summary={repository_show_summary}

        # Wether with color when use `-h` get help message.
        help_use_color={help_use_color}

        # The max line width when use `-h` get help message.
        help_max_line_width={help_max_line_width}
        """
    )

    # yapf: disable
    keys = [
        'gitprocessor_show_original', 'gitprocessor_use_recommend',
        'gitprocessor_interactive_color', 'gitprocessor_interactive_help_showtime',
        'codecounter_use_gitignore', 'codecounter_show_invalid', 'codecounter_result_format',
        'gitignore_generator_timeout',
        'repository_show_path', 'repository_show_remote', 'repository_show_branchs',
        'repository_show_lastest_log', 'repository_show_summary',
        'help_use_color', 'help_max_line_width'
    ]
    # yapf: enable

    gitprocessor_show_original = True
    gitprocessor_use_recommend = True
    gitprocessor_interactive_color = True
    gitprocessor_interactive_help_showtime = 1.5

    codecounter_use_gitignore = True
    codecounter_show_invalid = False
    codecounter_result_format = "table"  # table, simple
    _supported_result_format = ["table", "simple"]

    gitignore_generator_timeout = 60

    repository_show_path = True
    repository_show_remote = True
    repository_show_branchs = True
    repository_show_lastest_log = True
    repository_show_summary = False

    help_use_color = True
    help_max_line_width = 90

    # Store warning messages.
    warnings = []

    def __init__(self, path=None):
        super(Config, self).__init__()
        if not path:
            self.config_path = self.Conf_Path
        else:
            self.config_path = path
        conf = self.load_config()
        # from pprint import pprint

        # print(len(conf))
        # pprint(conf)
        for key in self.keys:
            if key in conf.keys() and conf[key] != "==error==":
                setattr(self, key, conf[key])

    def load_config(self):
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
                    key = key.strip()
                    line = line.strip().strip('"')
                    if key not in self.keys:
                        continue
                    if type(getattr(self, key)) == int:
                        try:
                            new_config[key] = int(line)
                        except ValueError:
                            self.warnings.append(
                                'Config key "{}" should be an integer!'.format(key)
                            )
                    if type(getattr(self, key)) == bool:
                        try:
                            # True values are y, yes, t, true, on and 1;
                            # false values are n, no, f, false, off and 0.
                            # Raises ValueError if val is anything else.
                            new_config[key] = bool(strtobool(line))
                        except ValueError:
                            self.warnings.append(
                                'Config key "{}" can only be True or False!'.format(key)
                            )
                    if type(getattr(self, key)) == str:
                        if "color" in key and not self.is_color(line):
                            self.warnings.append(
                                'Config key "{}" should be RGB, like: #FF0000'.format(
                                    key
                                )
                            )
                            continue
                        new_config[key] = str(line)
        except Exception as e:
            Log.error(str(e))

        if (
            "codecounter_result_format" in new_config
            and new_config["codecounter_result_format"]
            not in self._supported_result_format
        ):
            new_config["codecounter_result_format"] = "==error=="
            self.warnings.append(
                'Config key "{}" support must in {}'.format(
                    "codecounter_result_format", self._supported_result_format
                )
            )

        return new_config

    def is_color(self, v):
        return v and v.startswith("#") and len(v) == 7

    @classmethod
    def create_config_template(cls):
        if not os.path.isdir(PIGIT_HOME):
            os.makedirs(PIGIT_HOME, exist_ok=True)

        if os.path.exists(cls.Conf_Path) and not confirm(
            "Configuration exists, overwrite? [y/n]"
        ):
            return
        try:
            with open(
                cls.Conf_Path, "w" if os.path.isfile(cls.Conf_Path) else "x"
            ) as f:
                f.write(cls.Config_Template.format(version=__version__, **vars(cls)))
            print("Successful.")
        except Exception as e:
            # print(str(e))
            print("Failed, create config.")


CONFIG = Config()
if CONFIG.warnings:
    for warning in CONFIG.warnings:
        print(warning)
    CONFIG.warnings = []


#####################################################################
# Implementation of additional functions.                           #
#####################################################################
def introduce():
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

    color_print("Description:", Fx.b)
    color_print(
        (
            "  Terminal tool, help you use git more simple."
            " Support Linux and MacOS. Partial support for windows.\n"
            "  It use short command to replace the original command, like: \n"
            "  `pigit ws` -> `git status --short`, `pigit b` -> `git branch`.\n"
            "  Also you use `g -s` to get the all short command, have fun"
            " and good lucky.\n"
            "  The open source path: %s" % (TermColor.SkyBlue + Fx.underline + __url__)
        ),
        Fx.italic,
    )

    print("\nYou can use ", end="")
    color_print("-h", TermColor.Green, end="")
    print(" and ", end="")
    color_print("--help", TermColor.Green, end="")
    print(" to get help and more usage.\n")


def init_hook():
    try:
        signal.signal(signal.SIGINT, leave)
    except Exception as e:
        print(str(e))


def get_extra_cmds():
    import imp

    extra_cmd_path = PIGIT_HOME + "/extra_cmds.py"
    # print(extra_cmd_path)
    extra_cmds = {}
    if os.path.isfile(extra_cmd_path):
        try:
            extra_cmd = imp.load_source("extra_cmd", extra_cmd_path)
            extra_cmds = extra_cmd.extra_cmds
        except Exception:
            pass
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
    def __init__(self):
        super(Parser, self).__init__()
        self._parser = argparse.ArgumentParser(
            prog="pigit",
            description="If you want to use some original git commands, please use -- to indicate.",
            prefix_chars="-",
            formatter_class=CustomHelpFormatter,
        )
        self._parser.add_argument(
            "-C",
            "--complete",
            action="store_true",
            help="Add shell prompt script and exit.(Supported `bash`, `zsh`)",
        )
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
            % ", ".join(GitProcessor.Types),
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
            help=(
                "Count the number of codes and output them in tabular form.\n"
                "A given path can be accepted, and the default is the current directory."
            ),
        )
        self._parser.add_argument(
            "--create-ignore",
            type=str,
            metavar="TYPE",
            dest="ignore_type",
            help="Create a demo .gitignore file. Need one argument, support: [%s]"
            % ", ".join(GitignoreGenetor.Supported_Types.keys()),
        )
        self._parser.add_argument(
            "--create-config",
            action="store_true",
            help="Create a preconfigured file of git-tools.",
        )
        self._parser.add_argument(
            "--debug",
            action="store_true",
            help="Run in debug mode.",
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

    def parse(self, custom_commands=None):
        if custom_commands:
            return self._parser.parse_args(custom_commands)
        return self._parser.parse_args()


@time_it
def main(custom_commands=None):
    init_hook()

    parser = Parser()
    # parse custom comand, if has.
    if custom_commands is not None:
        stdargs = parser.parse(custom_commands)
    stdargs = parser.parse()
    # print(stdargs)

    # Setup log handle.
    LogHandle.setup_logging(
        debug=stdargs.debug,
        log_file=None if stdargs.out_log else LOG_PATH,
    )

    if stdargs.complete:
        completion_vars = {
            key: value.get("help", "") for key, value in Git_Cmds.items()
        }
        completion_vars.update(process_argparse(parser._parser))
        ShellCompletion(__project__, completion_vars, PIGIT_HOME).complete_and_use()
        raise SystemExit(0)

    if stdargs.config:
        git_local_config()

    if stdargs.information:
        repository_info(
            show_path=CONFIG.repository_show_path,
            show_remote=CONFIG.repository_show_remote,
            show_branches=CONFIG.repository_show_branchs,
            show_lastest_log=CONFIG.repository_show_lastest_log,
            show_summary=CONFIG.repository_show_summary,
        )

    if stdargs.create_config:
        Config.create_config_template()
        raise SystemExit(0)

    if stdargs.ignore_type:
        GitignoreGenetor().create_gitignore(
            stdargs.ignore_type,
            dir_path=Repository_Path,
            timeout=CONFIG.gitignore_generator_timeout,
        )
        raise SystemExit(0)

    if stdargs.count:
        path = stdargs.count if stdargs.count != "." else os.getcwd()
        CodeCounter(
            count_path=path,
            use_ignore=CONFIG.codecounter_use_gitignore,
            result_saved_path=COUNTER_PATH,
            result_format=CONFIG.codecounter_result_format,
        ).count_and_format_print(
            show_invalid=CONFIG.codecounter_show_invalid,
        )
        raise SystemExit(0)

    git_processor = GitProcessor(
        extra_cmds=get_extra_cmds(),
        use_recommend=CONFIG.gitprocessor_use_recommend,
        show_original=CONFIG.gitprocessor_show_original,
    )
    if stdargs.show_commands:
        git_processor.command_help()
        raise SystemExit(0)

    if stdargs.command_type:
        git_processor.command_help_by_type(stdargs.command_type)
        raise SystemExit(0)

    if stdargs.types:
        git_processor.type_help()
        raise SystemExit(0)

    if stdargs.command:
        command = stdargs.command
        git_processor.process_command(command, stdargs.args)
        raise SystemExit(0)

    if not list(filter(lambda x: x, vars(stdargs).values())):
        introduce()


if __name__ == "__main__":
    main()
