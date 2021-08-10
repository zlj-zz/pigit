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
__version__ = "1.0.7.bate.1"
__url__ = "https://github.com/zlj-zz/pigit.git"
__uri__ = __url__

__author__ = "Zachary Zhang"
__email__ = "zlj19971222@outlook.com"

__license__ = "MIT"
__copyright__ = "Copyright (c) 2021 Zachary"


import os
import re
import sys
import signal
import argparse
import logging
import logging.handlers
import textwrap
import time
import random
from math import sqrt, ceil
from distutils.util import strtobool
from collections import Counter

from .compat import input, B, get_terminal_size
from .utils import run_cmd, exec_cmd, confirm
from .str_utils import get_width, shorten
from .common import Color, Fx
from .model import File
from .decorator import time_it
from .codecounter import CodeCounter
from .shell_completion import ShellCompletion, process_argparse
from .gitignore import GitignoreGenetor


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


# For encoding.
Icon_Supported_Encoding = ["utf-8"]
System_Encoding = sys.getdefaultencoding().lower()
# TODO(zlj-zz): There are some problems with the output emotion on windows.
# ? In CMD, encoding is right, but emotion is error.
# ? In git bash, encoding is not right, but seem can't detection.
if not IS_WIN and System_Encoding in Icon_Supported_Encoding:
    Icon_Rainbow = "🌈"
    Icon_Smiler = "😊"
    Icon_Thinking = "🧐"
    Icon_Sorry = "😅"
else:
    Icon_Rainbow = "::"
    Icon_Smiler = "^_^"
    Icon_Thinking = "-?-"
    Icon_Sorry = "Orz"

try:
    import select, termios, fcntl, tty

    TERM_CONTROL = True
except Exception:
    TERM_CONTROL = False


#####################################################################
# Custom error.                                                     #
#####################################################################
class TermError(Exception):
    pass


#####################################################################
# Part of Utils.                                                    #
# Some tools and methods for global use. Also contains some special #
# global variables (readonly).                                      #
#####################################################################
Log = logging.getLogger(__name__)


def ensure_path(dir_path):
    """Determine whether the file path exists. If not, create a directory.

    Args:
        dir_path (str): Directory path, like: "~/.config/xxx"

    >>> ensure_path('~/.config/pigit')
    """
    if not os.path.isdir(dir_path):
        try:
            os.makedirs(dir_path, exist_ok=True)
        except PermissionError as e:
            err_echo("Don't have permission to create: %s" % dir_path)
            exit(1, e)
        except Exception as e:
            err_echo("An error occurred while creating %s" % dir_path)
            exit(1, e)


class LogHandle(object):
    """Set log handle.
    Attributes:
        FMT_NORMAL: Log style in normal mode.
        FMT_DEBUG: Log style in debug mode.

    Functions:
        setup_logging: setup log handle setting.

    Raises:
        SystemExit: When the log file cannot be written.
    """

    FMT_NORMAL = logging.Formatter(
        fmt="%(asctime)s %(levelname).4s %(message)s", datefmt="%H:%M:%S"
    )
    FMT_DEBUG = logging.Formatter(
        fmt="%(asctime)s.%(msecs)03d %(levelname).4s [%(name)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    @classmethod
    def setup_logging(cls, debug=False, log_file=None):
        root_logger = logging.getLogger()

        if debug:
            log_level = logging.DEBUG
            formatter = cls.FMT_DEBUG
        else:
            log_level = logging.INFO
            formatter = cls.FMT_NORMAL

        if log_file:
            if log_file is None:
                log_handle = logging.StreamHandler()
            else:
                dir_path = os.path.dirname(log_file)
                ensure_path(dir_path)
                try:
                    log_handle = logging.handlers.RotatingFileHandler(
                        log_file, maxBytes=1048576, backupCount=4
                    )
                except PermissionError:
                    print('No permission to write to "{}" directory!'.format(log_file))
                    raise SystemExit(1)

        log_handle.setFormatter(formatter)
        log_handle.setLevel(log_level)

        root_logger.addHandler(log_handle)
        root_logger.setLevel(0)


# Exit code.
EXIT_NORMAL = 0
EXIT_ERROR = 1


def leave(code, *args):
    """Exit program.

    Receive error code, error message. If the error code matches, print the
    error information to the log. Then the command line output prompt, and
    finally exit.

    Args:
        code: Exit code.
        *args: Other messages.
    """

    if code == EXIT_ERROR:
        Log.error(args)
        print("Please check {}".format(PIGIT_HOME))

    raise SystemExit(0)


def git_version():
    """Get Git version."""
    try:
        _, git_version_ = exec_cmd("git --version")
        if git_version_:
            return git_version_
        else:
            return None
    except Exception:
        Log.warning("Can not found Git in environment.")
        return None


# Not detected, the result is None
Git_Version = git_version()


def current_repository():
    """Get the current git repository path. If not, the path is empty."""
    err, path = exec_cmd("git rev-parse --git-dir")

    if err:
        return ""

    path = path.strip()
    if path == ".git":
        repository_path = os.getcwd()
    else:
        repository_path = path[:-5]
    return repository_path


Repository_Path = current_repository()
IS_Git_Repository = True if Repository_Path else False


class ConfigError(Exception):
    """Config error. Using by `Config`."""

    pass


class Config(object):
    Conf_Path = PIGIT_HOME + "/pigit.conf"
    Config_Template = textwrap.dedent(
        """
        #? Config file for pigit v. {version}
        # Git-tools -- pigit configuration.

        # Color settings for informational messages.
        # Only complete RGB values are accepted, such as: #FF0000
        okay_echo_color={okay_echo_color}
        warning_echo_color={warning_echo_color}
        error_echo_color={error_echo_color}

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
        'okay_echo_color', 'warning_echo_color', 'error_echo_color',
        'gitprocessor_show_original', 'gitprocessor_use_recommend',
        'gitprocessor_interactive_color', 'gitprocessor_interactive_help_showtime',
        'codecounter_use_gitignore', 'codecounter_show_invalid', 'codecounter_result_format',
        'gitignore_generator_timeout',
        'repository_show_path','repository_show_remote', 'repository_show_branchs',
        'repository_show_lastest_log','repository_show_summary',
        'help_use_color', 'help_max_line_width'
    ]
    # yapf: enable
    okay_echo_color = "#98FB98"  # PaleGreen
    warning_echo_color = "#FFD700"  # Gold
    error_echo_color = "#FF6347"  # Tomato

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
                    if not "=" in line:
                        # invalid line.
                        continue
                    key, line = line.split("=", maxsplit=1)
                    key = key.strip()
                    line = line.strip().strip('"')
                    if not key in self.keys:
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
        ensure_path(PIGIT_HOME)
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
# KeyBoard event.                                                    #
#####################################################################
class KeyEvent(object):
    """KeyBoard event class.

    Subclass:
        Raw: Set raw input mode for device.
        Nonblocking: Set nonblocking mode for device.

    Attributes:
        escape: Translation dictionary.
        _resized: windows resize handle.

    Functions:
        signal_init: Register signal events.
        signal_restore: Unregister signal events.
        sync_get_key: get one input value, will wait until get input.
    """

    class Raw(object):
        """Set raw input mode for device"""

        def __init__(self, stream):
            self.stream = stream
            self.fd = self.stream.fileno()

        def __enter__(self):
            # Get original fd descriptor.
            self.original_descriptor = termios.tcgetattr(self.stream)
            # Change the mode of the file descriptor fd to cbreak.
            tty.setcbreak(self.stream)

        def __exit__(self, type, value, traceback):
            termios.tcsetattr(self.stream, termios.TCSANOW, self.original_descriptor)

    class Nonblocking(object):
        """Set nonblocking mode for device"""

        def __init__(self, stream):
            self.stream = stream
            self.fd = self.stream.fileno()

        def __enter__(self):
            self.orig_fl = fcntl.fcntl(self.fd, fcntl.F_GETFL)
            fcntl.fcntl(self.fd, fcntl.F_SETFL, self.orig_fl | os.O_NONBLOCK)

        def __exit__(self, *args):
            fcntl.fcntl(self.fd, fcntl.F_SETFL, self.orig_fl)

    escape = {
        "\n": "enter",
        ("\x7f", "\x08"): "backspace",
        ("[A", "OA"): "up",
        ("[B", "OB"): "down",
        ("[D", "OD"): "left",
        ("[C", "OC"): "right",
        "[2~": "insert",
        "[3~": "delete",
        "[H": "home",
        "[F": "end",
        "[5~": "page_up",
        "[6~": "page_down",
        "\t": "tab",
        "[Z": "shift_tab",
        "OP": "f1",
        "OQ": "f2",
        "OR": "f3",
        "OS": "f4",
        "[15": "f5",
        "[17": "f6",
        "[18": "f7",
        "[19": "f8",
        "[20": "f9",
        "[21": "f10",
        "[23": "f11",
        "[24": "f12",
    }

    _resize_pipe_rd, _resize_pipe_wr = os.pipe()
    _resized = False

    @classmethod
    def _sigwinch_handler(cls, signum, frame=None):
        if not cls._resized:
            os.write(cls._resize_pipe_wr, B("R"))
        cls._resized = True

    @classmethod
    def signal_init(cls):
        signal.signal(signal.SIGWINCH, cls._sigwinch_handler)

    @classmethod
    def signal_restore(cls):
        signal.signal(signal.SIGWINCH, signal.SIG_DFL)

    @classmethod
    def sync_get_input(cls):
        while True:
            with cls.Raw(sys.stdin):
                if cls._resized:
                    cls._resized = False
                    clean_key = "windows resize"
                    return clean_key

                # * Wait 100ms for input on stdin then restart loop to check for stop flag
                if not select.select([sys.stdin], [], [], 0.1)[0]:
                    continue
                input_key = sys.stdin.read(1)
                if input_key == "\033":
                    # * Set non blocking to prevent read stall
                    with cls.Nonblocking(sys.stdin):
                        input_key += sys.stdin.read(20)
                        if input_key.startswith("\033[<"):
                            _ = sys.stdin.read(1000)
                # print(repr(input_key))
                if input_key == "\033":
                    clean_key = "escape"
                elif input_key == "\\":
                    clean_key = "\\"  # * Clean up "\" to not return escaped
                else:
                    for code in cls.escape:
                        if input_key.lstrip("\033").startswith(code):
                            clean_key = cls.escape[code]
                            break
                    else:
                        clean_key = input_key

                # print(clean_key)
                return clean_key


#####################################################################
# Part of Style.                                                    #
# Defines classes that generate colors and styles to beautify the   #
# output. The method of color printing is also defined.             #
#####################################################################


class CommandColor:
    """Terminal print color class."""

    Red = Color.fg("#FF6347")  # Tomato
    Green = Color.fg("#98FB98")  # PaleGreen
    DeepGreen = Color.fg("#A4BE8C")  # PaleGreen
    Yellow = Color.fg("#EBCB8C")
    Gold = Color.fg("#FFD700")  # Gold
    SkyBlue = Color.fg("#87CEFA")
    MediumVioletRed = Color.fg("#C71585")
    Symbol = {"+": Color.fg("#98FB98"), "-": Color.fg("#FF6347")}


def echo(msg, color="", style="", nl=True):
    """Print to terminal.

    Print special information with color and style according to the
    incoming parameters.

    Args:
        msg: A special message.
        color: Message color.
        style: Message style, like: [bold, underline].
        nl: Is there a line feed.
    """
    msg = "%s%s%s%s" % (style, color, msg, Fx.reset)
    if nl:
        msg += "\n"
    sys.stdout.write(msg)
    sys.stdout.flush()


def okay_echo(msg, nl=True):
    """Print green information."""
    echo("%s%s%s%s" % (Fx.b, Color.fg(CONFIG.okay_echo_color), msg, Fx.reset), nl=nl)


def warn_echo(msg, nl=True):
    """Print yellow information."""
    echo("%s%s%s%s" % (Fx.b, Color.fg(CONFIG.warning_echo_color), msg, Fx.reset), nl=nl)


def err_echo(msg, nl=True):
    """Print red information."""
    echo("%s%s%s%s" % (Fx.b, Color.fg(CONFIG.error_echo_color), msg, Fx.reset), nl=nl)


#####################################################################
# Part of command.                                                  #
#####################################################################
class InteractiveAdd(object):
    """Interactive operation git tree status."""

    def __init__(self, use_color=True, cursor=None, help_wait=1.5, debug=False):
        super(InteractiveAdd, self).__init__()
        self.use_color = use_color
        if not cursor:
            self.cursor = "→"
        elif len(cursor) == 1:
            self.cursor = cursor
        else:
            self.cursor = "→"
            print("The cursor symbol entered is not supported.")
        self.help_wait = help_wait
        self._min_height = 8
        self._min_width = 60
        self._debug = debug

    def get_status(self, max_width, ident=2):
        """Get the file tree status of GIT for processing and encapsulation.

        Args:
            max_width (int): The max length of display string.
            ident (int, option): Number of reserved blank characters in the header.

        Raises:
            Exception: Can't get tree status.

        Returns:
            (list[File]): Processed file status list.
        """

        file_items = []
        err, files = exec_cmd("git status -s -u --porcelain")
        if err:
            raise Exception("Can't get git status.")
        for file in files.rstrip().split("\n"):
            change = file[:2]
            staged_change = file[:1]
            unstaged_change = file[1:2]
            name = file[3:]
            untracked = change in ["??", "A ", "AM"]
            has_no_staged_change = staged_change in [" ", "U", "?"]
            has_merged_conflicts = change in ["DD", "AA", "UU", "AU", "UA", "UD", "DU"]
            has_inline_merged_conflicts = change in ["UU", "AA"]

            display_name = shorten(name, max_width - 3 - ident)
            # color full command.
            if unstaged_change != " ":
                if not has_no_staged_change:
                    display_str = "{}{}{}{} {}{}".format(
                        CommandColor.Green,
                        staged_change,
                        CommandColor.Red,
                        unstaged_change,
                        display_name,
                        Fx.reset,
                    )
                else:
                    display_str = "{}{} {}{}".format(
                        CommandColor.Red, change, display_name, Fx.reset
                    )
            else:
                display_str = "{}{} {}{}".format(
                    CommandColor.Green, change, display_name, Fx.reset
                )

            file_ = File(
                name=name,
                display_str=display_str if self.use_color else file,
                short_status=change,
                has_staged_change=not has_no_staged_change,
                has_unstaged_change=unstaged_change != " ",
                tracked=not untracked,
                deleted=unstaged_change == "D" or staged_change == "D",
                added=unstaged_change == "A" or untracked,
                has_merged_conflicts=has_merged_conflicts,
                has_inline_merged_conflicts=has_inline_merged_conflicts,
            )
            file_items.append(file_)

        return file_items

    def diff(self, file, tracked=True, cached=False, plain=False):
        """Gets the modification of the file.

        Args:
            file (str): file path relative to git.
            tracked (bool, optional): Defaults to True.
            cached (bool, optional): Defaults to False.
            plain (bool, optional): Wether need color. Defaults to False.

        Returns:
            (str): change string.
        """

        command = "git diff --submodule --no-ext-diff {plain} {cached} {tracked} {file}"

        if plain:
            _plain = "--color=never"
        else:
            _plain = "--color=always"

        if cached:
            _cached = "--cached"
        else:
            _cached = ""

        if not tracked:
            _tracked = "--no-index -- /dev/null"
        else:
            _tracked = "--"

        if "->" in file:  # rename
            file = file.split("->")[-1].strip()

        err, res = exec_cmd(
            command.format(plain=_plain, cached=_cached, tracked=_tracked, file=file)
        )
        if err:
            return "Can't get diff."
        return res.rstrip()

    def process_file(self, file):
        """Process file to change the status.

        Args:
            file (File): One processed file.
        """

        if file.has_merged_conflicts or file.has_inline_merged_conflicts:
            pass
        elif file.has_unstaged_change:
            run_cmd("git add -- {}".format(file.name))
        elif file.has_staged_change:
            if file.tracked:
                run_cmd("git reset HEAD -- {}".format(file.name))
            else:
                run_cmd("git rm --cached --force -- {}".format(file.name))

    # def loop(self, display_fn, dispaly_args=[], display_kwargs={}):
    #     pass

    def extra_occupied_rows(self, text, term_width):
        """Gets the number of additional lines occupied by a line of text in terminal.
        Used by `show_diff`.

        Args:
            text (str): text string.
            term_width (int): terminal width.

        Returns:
            (int): extra lines. min is 0.
        """

        count = 0
        for ch in text:
            count += get_width(ord(ch))
        return ceil(count / term_width) - 1

    def show_diff(self, file_obj):
        """Interactive display file diff.

        Args:
            file_obj (File): needed file.

        Raises:
            TermError: terminal size not enough.
        """

        width, height = get_terminal_size()

        # Initialize.
        cursor_row = 1
        display_range = [1, height - 1]

        stopping = False  # exit signal.

        def _process_diff(diff_list, term_width):
            """Process diff raw list.

            Generate a new list, in which each element is a tuple in the shape of (str, int).
            The first parameter is the displayed string, and the second is the additional
            row to be occupied under the current width.
            """
            new_list = []
            for line in diff_list:
                text = Fx.uncolor(line)
                count = 0
                for ch in text:
                    count += get_width(ord(ch))
                # [float] is to solve the division of python2 without retaining decimal places.
                new_list.append((line, ceil(count / term_width) - 1))
            return new_list

        # only need get once.
        diff_raw = self.diff(
            file_obj.name,
            file_obj.tracked,
            file_obj.has_staged_change,
            not self.use_color,
        ).split("\n")

        diff_ = _process_diff(diff_raw, width)
        if self._debug:  # debug mode print all occupied line num.
            echo(Fx.clear_)
            print(str([i[1] for i in diff_]))
            input()

        extra = 0  # Extra occupied row.
        while not stopping:
            echo(Fx.clear_)

            while cursor_row < display_range[0]:
                display_range = [i - 1 for i in display_range]
            while cursor_row + extra > display_range[1]:
                display_range = [i + 1 for i in display_range]

            extra = 0  # Return to zero and accumulate again.
            # Terminal outputs the text to be displayed.
            for index, data in enumerate(diff_, start=1):
                line, each_extra = data
                if display_range[0] <= index <= display_range[1] - extra:
                    if index == cursor_row:
                        print("{}{}{}".format(Color.bg("#6495ED"), line, Fx.reset))
                    else:
                        print(line)
                    extra += each_extra

            # TODO(zachary): sometime bug -- scroll with flash.
            input_key = KeyEvent.sync_get_input()
            if input_key in ["q", "escape"]:
                # exit.
                stopping = True
            elif input_key in ["j", "down"]:
                # select pre file.
                cursor_row += 1
                cursor_row = cursor_row if cursor_row < len(diff_) else len(diff_)
            elif input_key in ["k", "up"]:
                # select next file.
                cursor_row -= 1
                cursor_row = cursor_row if cursor_row > 1 else 1
            elif input_key in ["J"]:
                # scroll down 5 lines.
                cursor_row += 5
                cursor_row = cursor_row if cursor_row < len(diff_) else len(diff_)
            elif input_key in ["K"]:
                # scroll up 5 line
                cursor_row -= 5
                cursor_row = cursor_row if cursor_row > 1 else 1
            elif input_key == "windows resize":
                # get new term height.
                new_width, new_height = get_terminal_size()
                if new_height < self._min_height or new_width < self._min_width:
                    raise TermError("The minimum size of terminal should be 60 x 5.")
                # get size diff, reassign.
                line_diff = new_height - height
                width, height = new_width, new_height
                # get new display range.
                display_range[1] += line_diff
                diff_ = _process_diff(diff_raw, width)
            elif input_key == "?":
                # show help messages.
                echo(Fx.clear_)
                echo(
                    (
                        "k / ↑: select previous line.\n"
                        "j / ↓: select next line.\n"
                        "J: Scroll down 5 lines.\n"
                        "K: Scroll down 5 lines.\n"
                        "? : show help, wait {}s and exit.\n"
                    ).format(self.help_wait)
                )
                if self.help_wait == 0:
                    KeyEvent.sync_get_input()
                else:
                    time.sleep(self.help_wait)
            else:
                continue

    def discard_changed(self, file):
        """Discard file all changed.

        Args:
            file (File): file object.
        """
        echo(Fx.clear_)
        if confirm("discard all changed? [y/n]:"):
            if file.tracked:
                run_cmd("git checkout -- {}".format(file.name))
            else:
                os.remove(os.path.join(Repository_Path, file.name))

    def add_interactive(self, *args):
        """Interactive main method."""

        # Wether can into interactive.
        if not TERM_CONTROL:
            raise TermError("This behavior is not supported in the current system.")

        width, height = get_terminal_size()
        if height < self._min_height or width < self._min_width:
            raise TermError("The minimum size of terminal should be 60 x 5.")

        if self._debug:  # debug show.
            echo(Fx.clear_)
            print(width, height)
            time.sleep(1.5)

        # Initialize.
        cursor_row = 1
        cursor_icon = self.cursor
        display_range = [1, height - 1]

        stopping = False

        # Into new term page.
        echo(Fx.alt_screen + Fx.hide_cursor)

        file_items = self.get_status(width)
        try:
            KeyEvent.signal_init()

            # Start interactive.
            while not stopping:
                echo(Fx.clear_)
                while cursor_row < display_range[0]:
                    display_range = [i - 1 for i in display_range]
                while cursor_row > display_range[1]:
                    display_range = [i + 1 for i in display_range]

                # Print needed display part.
                for index, file in enumerate(file_items, start=1):
                    if display_range[0] <= index <= display_range[1]:
                        if index == cursor_row:
                            print("{} {}".format(cursor_icon, file.display_str))
                        else:
                            print("  " + file.display_str)

                input_key = KeyEvent.sync_get_input()
                if input_key in ["q", "escape"]:
                    # exit.
                    stopping = True
                elif input_key in ["j", "down"]:
                    # select pre file.
                    cursor_row += 1
                    cursor_row = (
                        cursor_row if cursor_row < len(file_items) else len(file_items)
                    )
                elif input_key in ["k", "up"]:
                    # select next file.
                    cursor_row -= 1
                    cursor_row = cursor_row if cursor_row > 1 else 1
                elif input_key in ["a", " "]:
                    self.process_file(file_items[cursor_row - 1])
                    file_items = self.get_status(width)
                elif input_key == "d":
                    self.discard_changed(file_items[cursor_row - 1])
                    file_items = self.get_status(width)
                elif input_key == "e":
                    editor = os.environ.get("EDITOR", None)
                    if editor:
                        run_cmd(
                            '{} "{}"'.format(
                                editor,
                                os.path.join(
                                    Repository_Path, file_items[cursor_row - 1].name
                                ),
                            )
                        )
                        file_items = self.get_status(width)
                    else:
                        pass
                elif input_key == "enter":
                    self.show_diff(file_items[cursor_row - 1])
                elif input_key == "windows resize":
                    # get new term height.
                    new_width, new_height = get_terminal_size()
                    if new_height < self._min_height or new_width < self._min_width:
                        raise TermError(
                            "The minimum size of terminal should be 60 x 5."
                        )
                    # get diff, reassign.
                    line_diff = new_height - height
                    height = new_height
                    # get new display range.
                    display_range[1] += line_diff
                elif input_key == "?":
                    echo(Fx.clear_)
                    echo(
                        (
                            "k / ↑: select previous file.\n"
                            "j / ↓: select next file.\n"
                            "a / space: toggle storage or unstorage file.\n"
                            "d: discard the file changed.\n"
                            "e: open file with default editor.\n"
                            "↲ : check file diff.\n"
                            "? : show help, wait {}s and exit.\n"
                        ).format(self.help_wait)
                    )
                    if self.help_wait == 0:
                        KeyEvent.sync_get_input()
                    else:
                        time.sleep(self.help_wait)
                else:
                    continue
        except KeyboardInterrupt:
            pass
        finally:
            # Whatever, unregister signal event and restore terminal at last.
            KeyEvent.signal_restore()
            echo(Fx.normal_screen + Fx.show_cursor)


class GitOptionSign:
    """Storage command type."""

    # command type.
    String = 1
    Func = 1 << 2
    # Accept parameters.
    No = 1 << 3
    Multi = 1 << 4


class GitProcessor(object):
    """Git short command processor.

    Subclass: _Function

    Attributes:
        Types (list): The short command type list.
        Git_Options (dict): Available short commands dictionaries.
            >>> d = {
            ...     'short_command': {
            ...         'state': GitOptionState.String,
            ...         'command': 'git status --short',
            ...         'help_msg': 'display repository status.'
            ...     }
            ... }
            >>> print(d)
    """

    Types = [
        "Branch",
        "Commit",
        "Conflict",
        "Fetch",
        "Index",
        "Log",
        "Merge",
        "Push",
        "Remote",
        "Stash",
        "Tag",
        "Working tree",
        "Setting",
    ]

    class _Function(object):
        """Command methods class.

        This class encapsulates some methods corresponding to command.
        All methods are [classmethod] or [staticmethod], must and only
        accept an `args` parameter -- a list of parameters to be processed.
        """

        @staticmethod
        def add(args):
            args_str = " ."
            if args:
                args_str = " ".join(args)

            echo(
                "{} Storage file: {}".format(
                    Icon_Rainbow, "all" if args_str.strip() == "." else args_str
                )
            )
            run_cmd("git add " + args_str)

        @staticmethod
        def fetch_remote_branch(args):
            branch = args[0] if len(args) > 1 else None

            if branch:
                run_cmd("git fetch origin {}:{} ".format(branch, branch))
            else:
                err_echo("This option need a branch name.")

        @staticmethod
        def set_email_and_username(args):
            print("Set the interactive environment of user name and email ...")
            __global = re.compile(r"\-\-global")
            for i in args:
                r = __global.search(i)
                if r is not None:
                    other = " --global "
                    print("Now set for global.")
                    break
            else:
                print("Now set for local.")
                other = " "

            name = input("Please input username:")
            while True:
                if not name:
                    err_echo("Name is empty.")
                    name = input("Please input username again:")
                else:
                    break

            email = input("Please input email:")
            email_re = re.compile(
                r"^[0-9a-zA-Z_]{0,19}@[0-9a-zA-Z]{1,13}\.[com,cn,net]{1,3}$"
            )
            while True:
                if email_re.match(email) is None:
                    err_echo("Bad mailbox format.")
                    email = input("Please input email again:")
                else:
                    break

            if run_cmd(
                GitProcessor.Git_Options["user"]["command"] + other + name
            ) and run_cmd(GitProcessor.Git_Options["email"]["command"] + other + email):
                okay_echo("Successfully set.")
            else:
                err_echo("Failed. Please check log.")

    Git_Options = {
        # Branch
        "b": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git branch ",
            "help-msg": "lists, creates, renames, and deletes branches.",
        },
        "bc": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git checkout -b ",
            "help-msg": "creates a new branch.",
        },
        "bl": {
            "state": GitOptionSign.String | GitOptionSign.No,
            "command": "git branch -vv ",
            "help-msg": "lists branches and their commits.",
        },
        "bL": {
            "state": GitOptionSign.String | GitOptionSign.No,
            "command": "git branch --all -vv ",
            "help-msg": "lists local and remote branches and their commits.",
        },
        "bs": {
            "state": GitOptionSign.String | GitOptionSign.No,
            "command": "git show-branch ",
            "help-msg": "lists branches and their commits with ancestry graphs.",
        },
        "bS": {
            "state": GitOptionSign.String | GitOptionSign.No,
            "command": "git show-branch --all ",
            "help-msg": "lists local and remote branches and their commits with ancestry graphs.",
        },
        "bm": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git branch --move ",
            "help-msg": "renames a branch.",
        },
        "bM": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git branch --move --force ",
            "help-msg": "renames a branch even if the new branch name already exists.",
        },
        # Commit
        "c": {
            "state": GitOptionSign.String | GitOptionSign.No,
            "command": "git commit --verbose ",
            "help-msg": "records changes to the repository.",
        },
        "ca": {
            "state": GitOptionSign.String | GitOptionSign.No,
            "command": "git commit --verbose --all ",
            "help-msg": "commits all modified and deleted files.",
        },
        "cA": {
            "state": GitOptionSign.String | GitOptionSign.No,
            "command": "git commit --verbose --patch ",
            "help-msg": "commits all modified and deleted files interactively",
        },
        "cm": {
            "state": GitOptionSign.String | GitOptionSign.No,
            "command": "git commit --verbose --message ",
            "help-msg": "commits with the given message.",
        },
        "co": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git checkout ",
            "help-msg": "checks out a branch or paths to the working tree.",
        },
        "cO": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git checkout --patch ",
            "help-msg": "checks out hunks from the index or the tree interactively.",
        },
        "cf": {
            "state": GitOptionSign.String | GitOptionSign.No,
            "command": "git commit --amend --reuse-message HEAD ",
            "help-msg": "amends the tip of the current branch reusing the same log message as HEAD.",
        },
        "cF": {
            "state": GitOptionSign.String | GitOptionSign.No,
            "command": "git commit --verbose --amend ",
            "help-msg": "amends the tip of the current branch.",
        },
        "cr": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git revert ",
            "help-msg": "reverts existing commits by reverting patches and recording new commits.",
        },
        "cR": {
            "state": GitOptionSign.String | GitOptionSign.No,
            "command": 'git reset "HEAD^" ',
            "help-msg": "removes the HEAD commit.",
        },
        "cs": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": 'git show --pretty=format:"%C(bold yellow)commit %H%C(auto)%d%n%C(bold)Author: %C(blue)%an <%ae> %C(reset)%C(cyan)%ai (%ar)%n%C(bold)Commit: %C(blue)%cn <%ce> %C(reset)%C(cyan)%ci (%cr)%C(reset)%n%+B"',
            "help-msg": "shows one or more objects (blobs, trees, tags and commits).",
        },
        # Conflict(C)
        "Cl": {
            "state": GitOptionSign.String | GitOptionSign.No,
            "command": "git --no-pager diff --diff-filter=U --name-only ",
            "help-msg": "lists unmerged files.",
        },
        "Ca": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git add git --no-pager diff --diff-filter=U --name-only ",
            "help-msg": "adds unmerged file contents to the index.",
        },
        "Ce": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git mergetool git --no-pager diff --diff-filter=U --name-only ",
            "help-msg": "executes merge-tool on all unmerged files.",
        },
        "Co": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git checkout --ours -- ",
            "help-msg": "checks out our changes for unmerged paths.",
        },
        "CO": {
            "state": GitOptionSign.String | GitOptionSign.No,
            "command": "git checkout --ours -- git --no-pager diff --diff-filter=U --name-only ",
            "help-msg": "checks out our changes for all unmerged paths.",
        },
        "Ct": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git checkout --theirs -- ",
            "help-msg": "checks out their changes for unmerged paths.",
        },
        "CT": {
            "state": GitOptionSign.String | GitOptionSign.No,
            "command": "git checkout --theirs -- git --no-pager diff --diff-filter=U --name-only ",
            "help-msg": "checks out their changes for all unmerged paths.",
        },
        # Fetch(f)
        "f": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git fetch ",
            "help-msg": "downloads objects and references from another repository.",
        },
        "fc": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git clone ",
            "help-msg": "clones a repository into a new directory.",
        },
        "fC": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git clone --depth=1 ",
            "help-msg": "clones a repository into a new directory clearly(depth:1).",
        },
        "fm": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git pull ",
            "help-msg": "fetches from and merges with another repository or local branch.",
        },
        "fr": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git pull --rebase ",
            "help-msg": "fetches from and rebase on top of another repository or local branch.",
        },
        "fu": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git fetch --all --prune && git merge --ff-only @{u} ",
            "help-msg": "removes un-existing remote-tracking references, fetches all remotes and merges.",
        },
        "fb": {
            "state": GitOptionSign.Func | GitOptionSign.No,
            "command": _Function.fetch_remote_branch,
            "help-msg": "fetch other branch to local as same name.",
        },
        # Index(i)
        "i": {
            "state": GitOptionSign.Func | GitOptionSign.No,
            "command": InteractiveAdd(
                use_color=CONFIG.gitprocessor_interactive_color,
                help_wait=CONFIG.gitprocessor_interactive_help_showtime,
            ).add_interactive,
            "help-msg": "interactive operation git tree status.",
        },
        "ia": {
            "state": GitOptionSign.Func | GitOptionSign.Multi,
            "command": _Function.add,
            "help-msg": "adds file contents to the index(default: all files).",
        },
        "iA": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git add --patch ",
            "help-msg": "adds file contents to the index interactively.",
        },
        "iu": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git add --update ",
            "help-msg": "adds file contents to the index (updates only known files).",
        },
        "id": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git diff --no-ext-diff --cached ",
            "help-msg": "displays changes between the index and a named commit (diff).",
        },
        "iD": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git diff --no-ext-diff --cached --word-diff ",
            "help-msg": "displays changes between the index and a named commit (word diff).",
        },
        "ir": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git reset ",
            "help-msg": "resets the current HEAD to the specified state.",
        },
        "iR": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git reset --patch ",
            "help-msg": "resets the current index interactively.",
        },
        "ix": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git rm --cached -r ",
            "help-msg": "removes files from the index (recursively).",
        },
        "iX": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git rm --cached -rf ",
            "help-msg": "removes files from the index (recursively and forced).",
        },
        # Log(l)
        "l": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git log --graph --all --decorate ",
            "help-msg": "displays the log with good format.",
        },
        "l1": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git log --graph --all --decorate --oneline ",
            "help-msg": "",
        },
        "ls": {
            "state": GitOptionSign.String | GitOptionSign.No,
            "command": 'git log --topo-order --stat --pretty=format:"%C(bold yellow)commit %H%C(auto)%d%n%C(bold)Author: %C(blue)%an <%ae> %C(reset)%C(cyan)%ai (%ar)%n%C(bold)Commit: %C(blue)%cn <%ce> %C(reset)%C(cyan)%ci (%cr)%C(reset)%n%+B" ',
            "help-msg": "displays the stats log.",
        },
        "ld": {
            "state": GitOptionSign.String | GitOptionSign.No,
            "command": 'git log --topo-order --stat --patch --pretty=format:"%C(bold yellow)commit %H%C(auto)%d%n%C(bold)Author: %C(blue)%an <%ae> %C(reset)%C(cyan)%ai (%ar)%n%C(bold)Commit: %C(blue)%cn <%ce> %C(reset)%C(cyan)%ci (%cr)%C(reset)%n%+B" ',
            "help-msg": "displays the diff log.",
        },
        "lv": {
            "state": GitOptionSign.String | GitOptionSign.No,
            "command": 'git log --topo-order --show-signature --pretty=format:"%C(bold yellow)commit %H%C(auto)%d%n%C(bold)Author: %C(blue)%an <%ae> %C(reset)%C(cyan)%ai (%ar)%n%C(bold)Commit: %C(blue)%cn <%ce> %C(reset)%C(cyan)%ci (%cr)%C(reset)%n%+B" ',
            "help-msg": "displays the log, verifying the GPG signature of commits.",
        },
        "lc": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git shortlog --summary --numbered ",
            "help-msg": "displays the commit count for each contributor in descending order.",
        },
        "lr": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git reflog ",
            "help-msg": "manages reflog information.",
        },
        # Merge(m)
        "m": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git merge ",
            "help-msg": "joins two or more development histories together.",
        },
        "ma": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git merge --abort ",
            "help-msg": "aborts the conflict resolution, and reconstructs the pre-merge state.",
        },
        "mC": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git merge --no-commit ",
            "help-msg": "performs the merge but does not commit.",
        },
        "mF": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git merge --no-ff ",
            "help-msg": "creates a merge commit even if the merge could be resolved as a fast-forward.",
        },
        "mS": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git merge -S ",
            "help-msg": "performs the merge and GPG-signs the resulting commit.",
        },
        "mv": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git merge --verify-signatures ",
            "help-msg": "verifies the GPG signature of the tip commit of the side branch being merged.",
        },
        "mt": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git mergetool ",
            "help-msg": "runs the merge conflict resolution tools to resolve conflicts.",
        },
        # Push(p)
        "p": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git push ",
            "help-msg": "updates remote refs along with associated objects.",
        },
        "pf": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git push --force-with-lease ",
            "help-msg": 'forces a push safely (with "lease").',
        },
        "pF": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git push --force ",
            "help-msg": "forces a push. ",
        },
        "pa": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git push --all ",
            "help-msg": "pushes all branches.",
        },
        "pA": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git push --all && git push --tags ",
            "help-msg": "pushes all branches and tags.",
        },
        "pt": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git push --tags ",
            "help-msg": "pushes all tags.",
        },
        "pc": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": 'git push --set-upstream origin "$(git symbolic-ref -q --short HEAD 2> /dev/null)" ',
            "help-msg": "pushes the current branch and adds origin as an upstream reference for it.",
        },
        "pp": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": 'git pull origin "$(git symbolic-ref -q --short HEAD 2> /dev/null)" && git push origin "$(git symbolic-ref -q --short HEAD 2> /dev/null)" ',
            "help-msg": "pulls and pushes the current branch from origin to origin.",
        },
        # Remote(R)
        "R": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git remote ",
            "help-msg": "manages tracked repositories.",
        },
        "Rl": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git remote --verbose ",
            "help-msg": "lists remote names and their URLs.",
        },
        "Ra": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git remote add ",
            "help-msg": "adds a new remote.",
        },
        "Rx": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git remote rm ",
            "help-msg": "removes a remote.",
        },
        "Rm": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git remote rename ",
            "help-msg": "renames a remote.",
        },
        "Ru": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git remote update ",
            "help-msg": "fetches remotes updates.",
        },
        "Rp": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git remote prune ",
            "help-msg": "prunes all stale remote tracking branches.",
        },
        "Rs": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git remote show ",
            "help-msg": "shows information about a given remote.",
        },
        "RS": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git remote set-url ",
            "help-msg": "changes URLs for a remote.",
        },
        # Stash(s)
        "s": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git stash ",
            "help-msg": "stashes the changes of the dirty working directory.",
        },
        "sp": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git stash pop ",
            "help-msg": "removes and applies a single stashed state from the stash list.",
        },
        "sl": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git stash list ",
            "help-msg": "lists stashed states.",
        },
        "sd": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git stash show",
            "help-msg": "",
        },
        "sD": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git stash show --patch --stat",
            "help-msg": "",
        },
        # 'sr': {
        #     'state': GitOptionState.STRING | GitOptionState.MULTI,
        #     'command': '_git_stash_recover ',
        #     'help-msg': '',
        # },
        # 'sc': {
        #     'state': GitOptionState.STRING | GitOptionState.MULTI,
        #     'command': '_git_clear_stash_interactive',
        #     'help-msg': '',
        # },
        # Tag (t)
        "t": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git tag ",
            "help-msg": "creates, lists, deletes or verifies a tag object signed with GPG.",
        },
        "ta": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git tag -a ",
            "help-msg": "create a new tag.",
        },
        "tx": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git tag --delete ",
            "help-msg": "deletes tags with given names.",
        },
        # Working tree(w)
        "ws": {
            "state": GitOptionSign.String | GitOptionSign.No,
            "command": "git status --short ",
            "help-msg": "displays working-tree status in the short format.",
        },
        "wS": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git status ",
            "help-msg": "displays working-tree status.",
        },
        "wd": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git diff --no-ext-diff ",
            "help-msg": "displays changes between the working tree and the index (diff).",
        },
        "wD": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git diff --no-ext-diff --word-diff ",
            "help-msg": "displays changes between the working tree and the index (word diff).",
        },
        "wr": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git reset --soft ",
            "help-msg": "resets the current HEAD to the specified state, does not touch the index nor the working tree.",
        },
        "wR": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git reset --hard ",
            "help-msg": "resets the current HEAD, index and working tree to the specified state.",
        },
        "wc": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git clean --dry-run ",
            "help-msg": "cleans untracked files from the working tree (dry-run).",
        },
        "wC": {
            "state": GitOptionSign.String | GitOptionSign.No,
            "command": "git clean -d --force ",
            "help-msg": "cleans untracked files from the working tree.",
        },
        "wm": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git mv ",
            "help-msg": "moves or renames files.",
        },
        "wM": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git mv -f ",
            "help-msg": "moves or renames files (forced).",
        },
        "wx": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git rm -r ",
            "help-msg": "removes files from the working tree and from the index (recursively).",
        },
        "wX": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git rm -rf ",
            "help-msg": "removes files from the working tree and from the index (recursively and forced).",
        },
        # Setting
        "savepd": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git config credential.helper store ",
            "help-msg": "Remember your account and password.",
        },
        "ue": {
            "state": GitOptionSign.Func | GitOptionSign.Multi,
            "command": _Function.set_email_and_username,
            "help-msg": "set email and username interactively.",
        },
        "user": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git config user.name ",
            "help-msg": "set username.",
        },
        "email": {
            "state": GitOptionSign.String | GitOptionSign.Multi,
            "command": "git config user.email ",
            "help-msg": "set user email.",
        },
        # 'clear': {
        #     'state': GitOptionState.STRING | GitOptionState.MULTI,
        #     'command': '_git_clear ${@:2:$((${#@}))} ',
        #     'help-msg': '',
        # },
        # 'ignore': {
        #     'state': GitOptionState.STRING | GitOptionState.MULTI,
        #     'command': '_git_ignore_files ${@:2:$((${#@}))} ',
        #     'help-msg': '',
        # },
    }

    @staticmethod
    def similar_command(command, all_commands):
        """Get the most similar command with K-NearestNeighbor.

        Args:
            command (str): command string.
            all_commands (list): The list of all command.

        Returns:
            (str): most similar command string.
        """
        #  The dictionary of letter frequency of all commands.
        words = {word: dict(Counter(word)) for word in all_commands}
        # Letter frequency of command.
        fre = dict(Counter(command))
        # The distance between the frequency of each letter in the command
        # to be tested and all candidate commands, that is the difference
        # between the frequency of letters.
        frequency_difference = {
            word: [fre[ch] - words[word].get(ch, 0) for ch in command]
            + [words[word][ch] - fre.get(ch, 0) for ch in word]
            for word in words
        }
        # Square of sum of squares of word frequency difference.
        frequency_sum_square = list(
            map(
                lambda item: [item[0], sqrt(sum(map(lambda i: i ** 2, item[1])))],
                frequency_difference.items(),
            )
        )

        def _comparison_reciprocal(a, b):
            """
            Returns how many identical letters
            are compared from the head. sigmod
            to 0 ~ 1.

            Args:
                a (str): need compare string.
                b (str): need compare string.
            """
            i = 0
            while i < len(a) and i < len(b):
                if a[i] == b[i]:
                    i += 1
                else:
                    break
            return 1 / (i + 1)

        # The value of `frequency_sum_square` is multiplied by the weight to find
        # the minimum.
        # Distance weight: compensate for the effect of length difference.
        # Compare Weight: The more similar the beginning, the higher the weight.
        min_frequency_command = min(
            frequency_sum_square,
            key=lambda item: item[1]
            * (
                len(command) / len(item[0])
                if len(command) / len(item[0])
                else len(item[0]) / len(command)
            )
            * _comparison_reciprocal(command, item[0]),
        )[0]
        return min_frequency_command

    @staticmethod
    def color_command(command):
        """Color the command string.
        prog: green;
        short command: yellow;
        arguments: skyblue;
        values: white.

        Args:
            command(str): valid command string.

        Returns:
            (str): color command string.
        """

        command_list = command.split(" ")
        color_command = (
            Fx.bold
            + CommandColor.DeepGreen
            + command_list.pop(0)
            + " "
            + CommandColor.Yellow
            + command_list.pop(0)
            + " "
            + Fx.unbold
            + Fx.italic
            + CommandColor.SkyBlue
        )
        while len(command_list) > 0:
            temp = command_list.pop(0)
            if temp.startswith("-"):
                color_command += temp + " "
            else:
                break

        color_command += Fx.reset
        if len(command_list) > 0:
            color_command += " ".join(command_list)

        return color_command

    @classmethod
    def process_command(
        cls, _command, args=None, use_recommend=False, show_original=True
    ):
        """Process command and arguments.

        Args:
            _command (str): short command string
            args (list|None, optional): command arguments. Defaults to None.

        Raises:
            SystemExit: not git.
            SystemExit: short command not right.
        """

        if Git_Version is None:
            err_echo("Git is not detected. Please install Git first.")
            raise SystemExit(0)

        option = cls.Git_Options.get(_command, None)

        if option is None:
            echo("Don't support this command, please try ", nl=False)
            warn_echo("g --show-commands")

            if use_recommend:  # check config.
                predicted_command = cls.similar_command(
                    _command, cls.Git_Options.keys()
                )
                echo(
                    "%s The wanted command is %s ?"
                    % (
                        Icon_Thinking,
                        CommandColor.Green + predicted_command + Fx.reset,
                    ),
                    nl=False,
                )
                if confirm("[y/n]:"):
                    cls.process_command(predicted_command, args=args)

            raise SystemExit(0)

        state = option.get("state", None)
        command = option.get("command", None)

        if state & GitOptionSign.No:
            if args:
                err_echo(
                    "The command does not accept parameters. Discard {}.".format(args)
                )
                args = []

        if state & GitOptionSign.Func:
            try:
                command(args)
            except TermError as e:
                err_echo(e)
        elif state & GitOptionSign.String:
            if args:
                args_str = " ".join(args)
                command = " ".join([command, args_str])
            if show_original:
                echo("{}  ".format(Icon_Rainbow), nl=False)
                echo(cls.color_command(command))
            run_cmd(command)
        else:
            pass

    ################################
    # Print command help message.
    ################################
    @classmethod
    def _generate_help_by_key(cls, _key, use_color=True):
        """Generate one help by given key.

        Args:
            _key (str): Short command string.
            use_color (bool, optional): Wether color help message. Defaults to True.

        Returns:
            (str): Help message of one command.
        """

        _msg = "    {key_color}{:<9}{reset}{}{command_color}{}{reset}"
        if use_color:
            _key_color = CommandColor.Green
            _command_color = CommandColor.Gold
        else:
            _key_color = _command_color = ""

        # Get help message and command.
        _help = cls.Git_Options[_key]["help-msg"]
        _command = cls.Git_Options[_key]["command"]

        # Process help.
        _help = _help + "\n" if _help else ""

        # Process command.
        if callable(_command):
            _command = "Callable: %s" % _command.__name__

        _command = shorten(_command, 70, placeholder="...")
        _command = " " * 13 + _command if _help else _command

        # Splicing and return.
        return _msg.format(
            _key,
            _help,
            _command,
            key_color=_key_color,
            command_color=_command_color,
            reset=Fx.reset,
        )

    @classmethod
    def command_help(cls):
        """Print help message."""
        echo("These are short commands that can replace git operations:")
        for key in cls.Git_Options.keys():
            msg = cls._generate_help_by_key(key)
            echo(msg)

    @classmethod
    def command_help_by_type(cls, command_type, use_recommend=False):
        """Print a part of help message.

        Print the help information of the corresponding part according to the
        incoming command type string. If there is no print error prompt for the
        type.

        Args:
            command_type (str): A command type of `TYPE`.
        """

        # Process received type.
        command_type = command_type.capitalize().strip()

        if command_type not in cls.Types:
            err_echo("There is no such type.")
            echo("Please use `", nl=False)
            echo("g --types", color=CommandColor.Green, nl=False)
            echo(
                "` to view the supported types.",
            )
            if use_recommend:
                predicted_type = cls.similar_command(command_type, cls.Types)
                echo(
                    "%s The wanted type is %s ?"
                    % (Icon_Thinking, CommandColor.Green + predicted_type + Fx.reset),
                    nl=False,
                )
                if confirm("[y/n]:"):
                    command_g(["-S", predicted_type])
            raise SystemExit(0)

        echo("These are the orders of {}".format(command_type))
        prefix = command_type[0].lower()
        for k in cls.Git_Options.keys():
            if k.startswith(prefix):
                msg = cls._generate_help_by_key(k)
                echo(msg)

    @classmethod
    def type_help(cls):
        """Print all command types with random color."""
        for t in cls.Types:
            echo(
                "{}{}  ".format(
                    Color.fg(
                        random.randint(70, 255),
                        random.randint(70, 255),
                        random.randint(70, 255),
                    ),
                    t,
                ),
                nl=False,
            )
        echo(Fx.reset)


#####################################################################
# Implementation of additional functions.                           #
#####################################################################
def git_local_config():
    """Print the local config of current git repository."""
    if IS_Git_Repository:
        _re = re.compile(r"\w+\s=\s.*?")
        try:
            with open(Repository_Path + "/.git/config", "r") as cf:
                for line in re.split(r"\r\n|\r|\n", cf.read()):
                    if line.startswith("["):
                        err_echo(line)
                    else:
                        if _re.search(line) is not None:
                            key, value = line.split("=")
                            echo(key, color=CommandColor.SkyBlue, nl=False)
                            print(
                                "="
                                + Fx.italic
                                + CommandColor.MediumVioletRed
                                + value
                                + Fx.reset
                            )
        except Exception as e:
            print(e)
            err_echo("Error reading configuration file.")
    else:
        err_echo("This directory is not a git repository yet.")


def repository_info(
    show_path=True,
    show_remote=True,
    show_branches=True,
    show_lastest_log=True,
    show_summary=True,
):
    """Print some information of the repository.

    repository: `Repository_Path`
    remote: read from '.git/conf'
    >>> all_branch = run_cmd_with_resp('git branch --all --color')
    >>> lastest_log = run_cmd_with_resp('git log -1')
    """

    echo("waiting ...", nl=False)

    error_str = CommandColor.Red + "Error getting" + Fx.reset

    # Print content.
    echo("\r[%s]        \n" % (Fx.b + "Repository Information" + Fx.reset,))
    if show_path:
        echo(
            "Repository: \n\t%s\n"
            % (CommandColor.SkyBlue + Repository_Path + Fx.reset,)
        )
    # Get remote url.
    if show_remote:
        try:
            with open(Repository_Path + "/.git/config", "r") as cf:
                config = cf.read()
                res = re.findall(r"url\s=\s(.*)", config)
                remote = "\n".join(
                    [
                        "\t%s%s%s%s" % (Fx.italic, CommandColor.SkyBlue, x, Fx.reset)
                        for x in res
                    ]
                )
        except Exception:
            remote = error_str
        echo("Remote: \n%s\n" % remote)
    # Get all branches.
    if show_branches:
        err, res = exec_cmd("git branch --all --color")
        if err:
            branches = "\t" + error_str
        else:
            branches = textwrap.indent(res, "\t")
        echo("Branches: \n%s\n" % branches)
    # Get the lastest log.
    if show_lastest_log:
        err, res = exec_cmd("git log --stat --oneline --decorate -1 --color")
        if err:
            git_log = "\t" + error_str
        else:
            # git_log = "\n".join(["\t" + x for x in res.strip().split("\n")])
            git_log = textwrap.indent(res, "\t")
        echo("Lastest log:\n%s\n" % git_log)
    # Get git summary.
    if show_summary:
        err, res = exec_cmd("git shortlog --summary --numbered")
        if err:
            summary = "\t" + error_str
        else:
            summary = textwrap.indent(res, "\t")
        echo("Summary:\n%s\n" % summary)


def introduce():
    """Print the description information."""

    # Print tools version and path.
    echo("[%s] version: %s" % (__project__, __version__), style=Fx.b)

    # Print git version.
    if Git_Version is None:
        echo("Don't found Git, maybe need install.")
    else:
        echo(Git_Version)

    # Print package path.
    echo("Path: ", style=Fx.b, nl=False)
    echo("%s\n" % __file__, color=CommandColor.SkyBlue, style=Fx.underline)

    echo("Description:", style=Fx.b)
    echo(
        (
            "  Terminal tool, help you use git more simple."
            " Support Linux and MacOS. Partial support for windows.\n"
            "  It use short command to replace the original command, like: \n"
            "  `g ws` -> `git status --short`, `g b` -> `git branch`.\n"
            "  Also you use `g -s` to get the all short command, have fun"
            " and good lucky.\n"
            "  The open source path: %s"
            % (CommandColor.SkyBlue + Fx.underline + __url__)
        ),
        style=Fx.italic,
    )

    echo("\nYou can use ", nl=False)
    echo("-h", color=CommandColor.Green, nl=False)
    echo(" and ", nl=False)
    echo("--help", color=CommandColor.Green, nl=False)
    echo(" to get help and more usage.\n")


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
            colors = [
                Color.fg("#FF6347"),  # Tomato
                Color.fg("#98FB98"),  # PaleGreen
                Color.fg("#EBCB8C"),  # Yellow
                Color.fg("#87CEFA"),  # SkyBlue
                # Color.fg("#FFC0CB"),  # Pink
            ]
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
            while True:
                _index = random.randint(0, self.color_len - 1)
                if _index == self._old_color:
                    continue
                else:
                    self._old_color = _index
                    break
            _color = self.colors[_index]
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


@time_it
def command_g(custom_commands=None):
    try:
        signal.signal(signal.SIGINT, leave)
    except Exception:
        pass

    args = argparse.ArgumentParser(
        prog="g",
        description="If you want to use some original git commands, please use -- to indicate.",
        prefix_chars="-",
        formatter_class=CustomHelpFormatter,
    )
    args.add_argument(
        "-C",
        "--complete",
        action="store_true",
        help="Add shell prompt script and exit.(Supported `bash`, `zsh`)",
    )
    args.add_argument(
        "-s",
        "--show-commands",
        action="store_true",
        help="List all available short command and wealth and exit.",
    )
    args.add_argument(
        "-S",
        "--show-command",
        type=str,
        metavar="TYPE",
        dest="command_type",
        help="According to given type(%s) list available short command and wealth and exit."
        % ", ".join(GitProcessor.Types),
    )
    args.add_argument(
        "-t",
        "--types",
        action="store_true",
        help="List all command types and exit.",
    )
    args.add_argument(
        "-f",
        "--config",
        action="store_true",
        help="Display the config of current git repository and exit.",
    )
    args.add_argument(
        "-i",
        "--information",
        action="store_true",
        help="Show some information about the current git repository.",
    )
    args.add_argument(
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
    args.add_argument(
        "--create-ignore",
        type=str,
        metavar="TYPE",
        dest="ignore_type",
        help="Create a demo .gitignore file. Need one argument, support: [%s]"
        % ", ".join(GitignoreGenetor.Supported_Types.keys()),
    )
    args.add_argument(
        "--create-config",
        action="store_true",
        help="Create a preconfigured file of git-tools.",
    )
    args.add_argument(
        "--debug",
        action="store_true",
        help="Run in debug mode.",
    )
    args.add_argument(
        "--out-log",
        action="store_true",
        help="Print log to console.",
    )
    args.add_argument(
        "-v",
        "--version",
        action="version",
        help="Show version and exit.",
        version="Version: %s" % __version__,
    )
    args.add_argument("command", nargs="?", type=str, help="Short git command.")
    args.add_argument("args", nargs="*", type=str, help="Command parameter list.")
    stdargs = args.parse_args()

    if custom_commands is not None:
        stdargs = args.parse_args(custom_commands)
    # print(stdargs)

    # Setup log handle.
    LogHandle.setup_logging(
        debug=stdargs.debug,
        log_file=None
        if stdargs.out_log
        else PIGIT_HOME + "/log/{}.log".format(__project__),
    )

    if stdargs.complete:
        completion_vars = {
            key: value["help-msg"] for key, value in GitProcessor.Git_Options.items()
        }
        completion_vars.update(process_argparse(args))
        ShellCompletion(completion_vars, PIGIT_HOME).complete_and_use()
        raise SystemExit(0)

    if stdargs.show_commands:
        GitProcessor.command_help()
        raise SystemExit(0)

    if stdargs.command_type:
        GitProcessor.command_help_by_type(
            stdargs.command_type, use_recommend=CONFIG.gitprocessor_use_recommend
        )
        raise SystemExit(0)

    if stdargs.types:
        GitProcessor.type_help()
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

    if stdargs.ignore_type:
        GitignoreGenetor().create_gitignore(
            stdargs.ignore_type,
            dir_path=Repository_Path,
            timeout=CONFIG.gitignore_generator_timeout,
        )
        raise SystemExit(0)

    if stdargs.create_config:
        Config.create_config_template()
        raise SystemExit(0)

    if stdargs.count:
        path = stdargs.count if stdargs.count != "." else os.getcwd()
        CodeCounter(
            count_path=path,
            use_ignore=CONFIG.codecounter_use_gitignore,
            result_saved_path=PIGIT_HOME + "/Counter",
            result_format=CONFIG.codecounter_result_format,
        ).count_and_format_print(
            show_invalid=CONFIG.codecounter_show_invalid,
        )
        raise SystemExit(0)

    if stdargs.command:
        command = stdargs.command
        GitProcessor.process_command(
            command,
            stdargs.args,
            use_recommend=CONFIG.gitprocessor_use_recommend,
            show_original=CONFIG.gitprocessor_show_original,
        )
        raise SystemExit(0)

    if not list(filter(lambda x: x, vars(stdargs).values())):
        introduce()


if __name__ == "__main__":
    command_g()
