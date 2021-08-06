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


__project__ = "git-tools"
__version__ = "1.0.5-beta.1"
__url__ = "https://github.com/zlj-zz/pygittools.git"
__uri__ = __url__

__author__ = "Zachary Zhang"
__email__ = "zlj19971222@outlook.com"

__license__ = "MIT"
__copyright__ = "Copyright (c) 2021 Zachary"


import os
import re
import sys
import stat
import subprocess
import signal
import argparse
import logging
import logging.handlers
import textwrap
import time
import random
import json
from math import sqrt, ceil
from collections import Counter
from functools import wraps


#####################################################################
# Part of compatibility.                                            #
# Handled the incompatibility between python2 and python3.          #
#####################################################################
PYTHON3 = sys.version_info > (3, 0)
if PYTHON3:
    input = input
    range = range

    import configparser

    configparser = configparser

    import urllib.request

    urlopen = urllib.request.urlopen
else:
    input = raw_input
    range = xrange

    import ConfigParser

    configparser = ConfigParser

    import urllib2

    urlopen = urllib2.urlopen

# For windows.
IS_WIN = sys.platform.lower().startswith("win")
if IS_WIN:
    USER_HOME = os.environ["USERPROFILE"]
    TOOLS_HOME = USER_HOME + "/pygittools"
else:
    USER_HOME = os.environ["HOME"]
    TOOLS_HOME = USER_HOME + "/.config/pygittools"

# For windows print color.
if os.name == "nt":
    os.system("")

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

    >>> ensure_path('~/.config/pygittools')
    """
    if not os.path.isdir(dir_path):
        try:
            os.makedirs(dir_path, exist_ok=True)
        except PermissionError as e:
            err("Don't have permission to create: %s" % dir_path)
            exit(1, e)
        except Exception as e:
            err("An error occurred while creating %s" % dir_path)
            exit(1, e)


def shorten(text, width, placeholder="...", front=False):
    """Truncate exceeded characters.

    Args:
        text (str): Target string.
        width (int): Limit length.
        placeholder (str): Placeholder string. Defaults to "..."
        front (bool): Head hidden or tail hidden. Defaults to False.

    Returns:
        (str): shorten string.

    >>> shorten('Hello world!', 5, placeholder='^-')
    """
    if len(text) > width:
        if front:
            _text = placeholder + text[-width + len(placeholder) :]
        else:
            _text = text[: width - len(placeholder)] + placeholder
    else:
        _text = text

    return _text


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
        print("Please check {}".format(TOOLS_HOME))

    raise SystemExit(0)


def run_cmd(*args):
    """Run system command.

    Returns:
        (bool): Wether run successful.

    >>> with subprocess.Popen("git status", shell=True) as proc:
    >>>    proc.wait()
    """

    try:
        with subprocess.Popen(" ".join(args), shell=True) as proc:
            proc.wait()
        return True
    except Exception as e:
        Log.warning(e)
        return False


def exec_cmd(*args):
    """Run system command and get result.

    Returns:
        (str, str): Error string and result string.

    >>> proc = subprocess.Popen(
    ...    "git --version", stderr=subprocess.PIPE, stdout=subprocess.PIPE, shell=True
    ... )
    >>> res = proc.stdout.read().decode()
    >>> err = proc.stderr.read().decode()
    >>> print(err, res)
    """

    try:
        proc = subprocess.Popen(
            " ".join(args), stderr=subprocess.PIPE, stdout=subprocess.PIPE, shell=True
        )
        res = proc.stdout.read().decode()
        err = proc.stderr.read().decode()
        proc.kill()
        return err, res
    except Exception as e:
        Log.warning(e)
        print(e)
        return e, ""


def confirm(text="", default=True):
    """Obtain confirmation results.
    Args:
        text (str): Confirmation prompt.
        default (bool): Result returned when unexpected input.

    Returns:
        (bool): Confirm result.

    >>> confirm('[y/n] (default: yes):')
    """
    input_command = input(text).strip().lower()
    if input_command in ["n", "no"]:
        return False
    elif input_command in ["y", "yes"]:
        return True
    else:
        return default


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


class Config(object):
    """Configuration class.

    Attributes:
        Conf_Path (str): configuration path.
        Conf_Template (str): configuration template.

    Functions:
        create_config_template (classmethod): create a config file use path.
    """

    Conf_Path = TOOLS_HOME + "/config.cfg"

    Conf_Template = textwrap.dedent(
        """\
        # Git-tools configuration.
        # Configuration language which provides a structure similar to what’s found in Microsoft Windows INI files.
        # For Boolean value setting, please fill in `yes` or `no`.


        # Color settings for informational messages.
        # Only complete RGB values are accepted, such as: #FF0000
        [Color]
        RightColor = #98FB98
        WarningColor = #FFD700
        ErrorColor = #FF6347


        [CodeCounter]
        # Whether to use the ignore configuration of the `.gitignore` file.
        UseGitignore = yes

        # Wether show files that cannot be counted.
        ShowInvalid = no

        # Output format of statistical results.
        # Supported: [table, simple]
        # When the command line width is not enough, the `simple ` format is forced.
        ResultFormat = table


        [GitignoreGenerator]
        # Timeout for getting `.gitignore` template.
        Timeout = 60


        [RepositoryInfo]
        ShowPath = yes
        ShowRemote = yes
        ShowBranchs = yes
        ShowLastestLog = yes
        ShowSummary = no


        [Help]
        UseColor = yes
        LineWidth = 90
        # Is it recommended to correct when entering wrong commands.
        UseRecommendation = yes
        """
    )

    ##########################################
    # Default values for configuration.
    ##########################################

    right_color = "#98FB98"  # PaleGreen
    warning_color = "#FFD700"  # Gold
    error_color = "#FF6347"  # Tomato

    use_gitignore = True
    show_invalid = False
    result_format = "simple"  # table, simple
    _supported_result_format = ["table", "simple"]

    timeout = 60

    show_path = True
    show_remote = True
    show_branchs = True
    show_lastest_log = True
    show_summary = False

    use_color = True
    line_width = 90
    use_recommend = False

    def __init__(self):
        super(Config, self).__init__()
        self.conf = configparser.ConfigParser(allow_no_value=True)
        self.conf.read(self.Conf_Path)
        sections = self.conf.sections()

        if "Color" in sections:
            right_color = self.right_color = self.conf["Color"].get("RightColor")
            if self.is_color(right_color):
                self.right_color = right_color

            warning_color = self.warning_color = self.conf["Color"].get("WarningColor")
            if self.is_color(warning_color):
                self.warning_color = warning_color

            error_color = self.error_color = self.conf["Color"].get("ErrorColor")
            if self.is_color(error_color):
                self.error_color = error_color

        if "CodeCounter" in sections:
            try:
                self.use_gitignore = self.conf["CodeCounter"].getboolean("UseGitignore")
            except Exception:
                pass

            try:
                self.show_invalid = self.conf["CodeCounter"].getboolean("ShowInvalid")
            except Exception:
                pass

            result_format = self.conf["CodeCounter"].get("ResultFormat")
            if result_format and result_format in self._supported_result_format:
                self.result_format = result_format

        if "GitignoreGenerator" in sections:
            try:
                self.timeout = self.conf["GitignoreGenerator"].getint("Timeout")
            except Exception:
                pass

        if "RepositoryInfo" in sections:
            try:
                self.show_path = self.conf["RepositoryInfo"].getboolean("ShowPath")
            except Exception:
                pass

            try:
                self.show_remote = self.conf["RepositoryInfo"].getboolean("ShowRemote")
            except Exception:
                pass

            try:
                self.show_branchs = self.conf["RepositoryInfo"].getboolean(
                    "ShowBranchs"
                )
            except Exception:
                pass

            try:
                self.show_lastest_log = self.conf["RepositoryInfo"].getboolean(
                    "ShowLastestLog"
                )
            except Exception:
                pass

            try:
                self.show_summary = self.conf["RepositoryInfo"].getboolean(
                    "ShowSummary"
                )
            except Exception:
                pass

        if "Help" in sections:
            try:
                self.use_color = self.conf["Help"].getboolean("UseColor")
            except Exception:
                pass

            try:
                self.line_width = self.conf["Help"].getint("LineWidth")
            except Exception:
                pass

            try:
                self.use_recommend = self.conf["Help"].getboolean("UseRecommendation")
            except Exception:
                pass

    def is_color(self, v):
        return v and v.startswith("#") and len(v) == 7

    @classmethod
    def create_config_template(cls):
        ensure_path(TOOLS_HOME)
        if os.path.exists(cls.Conf_Path) and not confirm(
            "Configuration exists, overwrite? [y/n]"
        ):
            return
        try:
            with open(cls.Conf_Path, "w") as f:
                f.write(cls.Conf_Template)
            print("Successful.")
        except Exception:
            print("Failed, create config.")


CONFIG = Config()


def time_testing(fn):
    """Print the overall running time.
    When recursive calls exist, only the outermost layer is printed.
    """
    time_testing.deep = 0

    @wraps(fn)
    def wrap_(*args, **kwargs):
        time_testing.deep += 1
        start_time = time.time()
        res = None
        try:
            res = fn(*args, **kwargs)
        except SystemExit:
            pass
        time_testing.deep -= 1
        if time_testing.deep == 0:
            print("\nruntime: %fs" % (time.time() - start_time))
        return res

    return wrap_


#####################################################################
# Part of Style.                                                    #
# Defines classes that generate colors and styles to beautify the   #
# output. The method of color printing is also defined.             #
#####################################################################
class Color(object):
    """Holds representations for a 24-bit color value

    __init__(color, depth="fg", default=False)
        -- color accepts 6 digit hexadecimal: string "#RRGGBB", 2 digit
            hexadecimal: string "#FF" or decimal RGB "255 255 255" as a string.
        -- depth accepts "fg" or "bg"
    __call__(*args) joins str arguments to a string and apply color
    __str__ returns escape sequence to set color
    __iter__ returns iteration over red, green and blue in integer values of 0-255.

    * Values:
        .hexa: str
        .dec: Tuple[int, int, int]
        .red: int
        .green: int
        .blue: int
        .depth: str
        .escape: str
    """

    # hexa: str
    # dec: Tuple[int, int, int]
    # red: int
    # green: int
    # blue: int
    # depth: str
    # escape: str
    # default: bool

    TRUE_COLOR = False

    def __init__(self, color, depth="fg", default=False):
        self.depth = depth
        self.default = default
        try:
            if not color:
                self.dec = (-1, -1, -1)
                self.hexa = ""
                self.red = self.green = self.blue = -1
                self.escape = "\033[49m" if depth == "bg" and default else ""
                return

            elif color.startswith("#"):
                self.hexa = color
                if len(self.hexa) == 3:
                    self.hexa += self.hexa[1:3] + self.hexa[1:3]
                    c = int(self.hexa[1:3], base=16)
                    self.dec = (c, c, c)
                elif len(self.hexa) == 7:
                    self.dec = (
                        int(self.hexa[1:3], base=16),
                        int(self.hexa[3:5], base=16),
                        int(self.hexa[5:7], base=16),
                    )
                else:
                    raise ValueError(
                        "Incorrectly formatted hexadecimal rgb string: {}".format(
                            self.hexa
                        )
                    )

            else:
                c_t = tuple(map(int, color.split(" ")))
                if len(c_t) == 3:
                    self.dec = c_t  # type: ignore
                else:
                    raise ValueError('RGB dec should be "0-255 0-255 0-255"')

            ct = self.dec[0] + self.dec[1] + self.dec[2]
            if ct > 255 * 3 or ct < 0:
                raise ValueError("RGB values out of range: {}".format(color))
        except Exception:
            # errlog.exception(str(e))
            self.escape = ""
            return

        if self.dec and not self.hexa:
            self.hexa = "%s%s%s" % (
                hex(self.dec[0]).lstrip("0x").zfill(2),
                hex(self.dec[1]).lstrip("0x").zfill(2),
                hex(self.dec[2]).lstrip("0x").zfill(2),
            )

        if self.dec and self.hexa:
            self.red, self.green, self.blue = self.dec
            self.escape = "\033[%s;2;%sm" % (
                38 if self.depth == "fg" else 48,
                ";".join(str(c) for c in self.dec),
            )

        if Color.TRUE_COLOR:
            self.escape = "{}".format(
                self.truecolor_to_256(rgb=self.dec, depth=self.depth)
            )

    def __str__(self):
        return self.escape

    def __repr__(self):
        return repr(self.escape)

    def __iter__(self):
        for c in self.dec:
            yield c

    # def __call__(self, *args: str) -> str:
    #     if len(args) < 1:
    #         return ""
    #     return f'{self.escape}{"".join(args)}{getattr(Term, self.depth)}'

    @staticmethod
    def truecolor_to_256(rgb, depth="fg"):
        out = ""
        pre = "\033[{};5;".format("38" if depth == "fg" else "48")

        greyscale = (rgb[0] // 11, rgb[1] // 11, rgb[2] // 11)
        if greyscale[0] == greyscale[1] == greyscale[2]:
            out = "{}{}m".format(pre, 232 + greyscale[0])
        else:
            out = "{}{}m".format(
                pre,
                round(rgb[0] / 51) * 36
                + round(rgb[1] / 51) * 6
                + round(rgb[2] / 51)
                + 16,
            )

        return out

    @staticmethod
    def escape_color(hexa="", r=0, g=0, b=0, depth="fg"):
        """Returns escape sequence to set color
        * accepts either 6 digit hexadecimal hexa="#RRGGBB", 2 digit hexadecimal: hexa="#FF"
        * or decimal RGB: r=0-255, g=0-255, b=0-255
        * depth="fg" or "bg"
        """
        dint = 38 if depth == "fg" else 48
        color = ""
        if hexa:
            try:
                if len(hexa) == 3:
                    c = int(hexa[1:], base=16)
                    if Color.TRUE_COLOR:
                        color = "\033[{};2;{};{};{}m".format(dint, c, c, c)
                    else:
                        color = Color.truecolor_to_256(rgb=(c, c, c), depth=depth)
                elif len(hexa) == 7:
                    if Color.TRUE_COLOR:
                        color = "\033[{};2;{};{};{}m".format(
                            dint,
                            int(hexa[1:3], base=16),
                            int(hexa[3:5], base=16),
                            int(hexa[5:7], base=16),
                        )
                    else:
                        color = "{}".format(
                            Color.truecolor_to_256(
                                rgb=(
                                    int(hexa[1:3], base=16),
                                    int(hexa[3:5], base=16),
                                    int(hexa[5:7], base=16),
                                ),
                                depth=depth,
                            )
                        )
            except ValueError:
                # errlog.exception(f'{e}')
                pass
        else:
            if Color.TRUE_COLOR:
                color = "\033[{};2;{};{};{}m".format(dint, r, g, b)
            else:
                color = "{}".format(Color.truecolor_to_256(rgb=(r, g, b), depth=depth))
        return color

    @classmethod
    def fg(cls, *args):
        if len(args) > 2:
            return cls.escape_color(r=args[0], g=args[1], b=args[2], depth="fg")
        else:
            return cls.escape_color(hexa=args[0], depth="fg")

    @classmethod
    def bg(cls, *args):
        if len(args) > 2:
            return cls.escape_color(r=args[0], g=args[1], b=args[2], depth="bg")
        else:
            return cls.escape_color(hexa=args[0], depth="bg")


if not PYTHON3:
    Color.TRUE_COLOR = True


class Fx(object):
    """Text effects
    * trans(string: str): Replace whitespace with escape move right to not
        overwrite background behind whitespace.
    * uncolor(string: str) : Removes all 24-bit color and returns string .
    """

    start = "\033["  # * Escape sequence start
    sep = ";"  # * Escape sequence separator
    end = "m"  # * Escape sequence end
    # * Reset foreground/background color and text effects
    reset = rs = "\033[0m"
    bold = b = "\033[1m"  # * Bold on
    unbold = ub = "\033[22m"  # * Bold off
    dark = d = "\033[2m"  # * Dark on
    undark = ud = "\033[22m"  # * Dark off
    italic = i = "\033[3m"  # * Italic on
    unitalic = ui = "\033[23m"  # * Italic off
    underline = u = "\033[4m"  # * Underline on
    ununderline = uu = "\033[24m"  # * Underline off
    blink = bl = "\033[5m"  # * Blink on
    unblink = ubl = "\033[25m"  # * Blink off
    strike = s = "\033[9m"  # * Strike / crossed-out on
    unstrike = us = "\033[29m"  # * Strike / crossed-out off

    # * Precompiled regex for finding a 24-bit color escape sequence in a string
    color_re = re.compile(r"\033\[\d+;\d?;?\d*;?\d*;?\d*m")

    @staticmethod
    def trans(string):
        return string.replace(" ", "\033[1C")

    @classmethod
    def uncolor(cls, string):
        return cls.color_re.sub("", string)


class Cursor:
    """Class with collection of cursor movement functions:
    Functions:
        .t[o](line, column)
        .r[ight](columns)
        .l[eft](columns)
        .u[p](lines)
        .d[own](lines)
        .save()
        .restore()
    """

    @staticmethod
    def to(line, col):
        # * Move cursor to line, column
        return "\033[{};{}f".format(line, col)

    @staticmethod
    def right(dx):
        return "\033[{}C".format(dx)

    @staticmethod
    def left(dx):
        return "\033[{}D".format(dx)

    @staticmethod
    def up(dy):
        return "\033[{}A".format(dy)

    @staticmethod
    def down(dy):
        return "\033[{}B".format(dy)

    save = "\033[s"  # * Save cursor position
    restore = "\033[u"  # * Restore saved cursor postion
    t = to
    r = right
    l = left
    u = up
    d = down


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


def okay(msg, nl=True):
    """Print green information."""
    echo("%s%s%s%s" % (Fx.b, Color.fg(CONFIG.right_color), msg, Fx.reset), nl=nl)


def warn(msg, nl=True):
    """Print yellow information."""
    echo("%s%s%s%s" % (Fx.b, Color.fg(CONFIG.warning_color), msg, Fx.reset), nl=nl)


def err(msg, nl=True):
    """Print red information."""
    echo("%s%s%s%s" % (Fx.b, Color.fg(CONFIG.error_color), msg, Fx.reset), nl=nl)


#####################################################################
# Part of command.                                                  #
#####################################################################
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
                err("This option need a branch name.")

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
                    err("Name is empty.")
                    name = input("Please input username again:")
                else:
                    break

            email = input("Please input email:")
            email_re = re.compile(
                r"^[0-9a-zA-Z_]{0,19}@[0-9a-zA-Z]{1,13}\.[com,cn,net]{1,3}$"
            )
            while True:
                if email_re.match(email) is None:
                    err("Bad mailbox format.")
                    email = input("Please input email again:")
                else:
                    break

            if run_cmd(
                GitProcessor.Git_Options["user"]["command"] + other + name
            ) and run_cmd(GitProcessor.Git_Options["email"]["command"] + other + email):
                okay("Successfully set.")
            else:
                err("Failed. Please check log.")

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
    def process_command(cls, _command, args=None):
        """Process command and arguments.

        Args:
            _command (str): short command string
            args (list|None, optional): command arguments. Defaults to None.

        Raises:
            SystemExit: not git.
            SystemExit: short command not right.
        """

        if Git_Version is None:
            err("Git is not detected. Please install Git first.")
            raise SystemExit(0)

        option = cls.Git_Options.get(_command, None)

        if option is None:
            echo("Don't support this command, please try ", nl=False)
            warn("g --show-commands")

            if CONFIG.use_recommend:  # check config.
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
                err("The command does not accept parameters. Discard {}.".format(args))
                args = []

        if state & GitOptionSign.Func:
            command(args)
        elif state & GitOptionSign.String:
            if args:
                args_str = " ".join(args)
                command = " ".join([command, args_str])
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
    def command_help_by_type(cls, command_type):
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
            err("There is no such type.")
            echo("Please use `", nl=False)
            echo("g --types", color=CommandColor.Green, nl=False)
            echo(
                "` to view the supported types.",
            )
            if CONFIG.use_recommend:
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
# Injection Completion Script.                                      #
#####################################################################
class Completion(object):
    """Implement and inject help classes for completion scripts.

    Attributes:
        _TEMPLATE_ZSH (str): zsh completion template.
        _TEMPLATE_BASH (str): bash completion template.
        Supported_Shell (list): supported shell list.
    """

    _TEMPLATE_ZSH = textwrap.dedent(
        """\
        #compdef g

        complete_g(){
        local curcontext="$curcontext" state line ret=1
        typeset -A opt_args

        _alternative\\
          \'args:options arg:((\\
            -C\:"Add shell prompt script and exit.(Supported `bash`, `zsh`)"\\
            --complete\:"Add shell prompt script and exit.(Supported `bash`, `zsh`)"\\
            -s\:"List all available short command and wealth and exit."\\
            --show-commands\:"List all available short command and wealth and exit."\\
            -S\:"According to given type list available short command and wealth and exit."\\
            --show-command\:"According to given type list available short command and wealth and exit."\\
            -t\:"List all command types and exit."\\
            --types\:"List all command types and exit."\\
            -f\:"Display the config of current git repository and exit."\\
            --config\:"Display the config of current git repository and exit."\\
            -i\:"Show some information about the current git repository."\\
            --information\:"Show some information about the current git repository."\\
            -v\:"Show version and exit."\\
            --version\:"Show version and exit."\\
            --create-ignore\:"Create a demo .gitignore file. Need one argument"\\
            --debug\:"Run in debug mode."\\
            --out-log\:"Print log to console."\\
            -c\:"Count the number of codes and output them in tabular form."\\
            --count\:"Count the number of codes and output them in tabular form."\\
            --create-config\:"Create config."\\

            %s
          ))\'\\
          'files:filename:_files'
        return ret
        }

        compdef complete_g g
    """
    )

    _TEMPLATE_BASH = textwrap.dedent(
        """\
        #!/usr/env bash

        _complete_g(){
        if [[ "${COMP_CWORD}" == "1" ]];then
            COMP_WORD="-C --complete -s --show-commands -S --show-command -t --types\\
                -f --config -i --information -v --version --create-ignore\\
                --debug --out-log -c --count --create-config\\
                %s"
            COMPREPLY=($(compgen -W "$COMP_WORD" -- ${COMP_WORDS[${COMP_CWORD}]}))
        fi
        }

        complete -F _complete_g g
    """
    )

    # TODO: support fish completion.
    Supported_Shell = ["zsh", "bash"]

    @staticmethod
    def get_current_shell():
        """Gets the currently used shell.

        Returns:
            (str): Current shell string.
        """
        current_shell = ""
        _, resp = exec_cmd("echo $SHELL")
        if resp:
            current_shell = resp.split("/")[-1].strip()
        return current_shell.lower()

    @staticmethod
    def ensure_config_path(file_name):
        """Check config path.

        Check whether the configuration directory exists, if not, try to create
        it. Failed to exit, successfully returned to complete the file path.

        Args:
            file_name (str): Completion prompt script name.

        Returns:
            file_path (str): Full path of completion prompt script.
        """
        Log.debug("{}, {}".format(TOOLS_HOME, file_name))
        ensure_path(TOOLS_HOME)

        return "{}/{}".format(TOOLS_HOME, file_name)

    @classmethod
    def generate_resource(cls, shell):
        """Generate completion scirpt.

        Generate the completion script of the corresponding shell according to
        the template.

        Args:
            shell (str): Current used shell.

        Returns:
            (str): completion file name.
            (str): completion source.
            (str): shell config path.
        """

        if shell == "zsh":
            name = "zsh_comp"
            template = cls._TEMPLATE_ZSH
            config_path = USER_HOME + "/.zshrc"

            def gen_completion():
                vars = []

                for k in GitProcessor.Git_Options.keys():
                    desc = GitProcessor.Git_Options[k]["help-msg"]
                    if not desc:
                        desc = "no description."
                    vars.append('    {}\\:"{}"\\'.format(k, desc))

                return ("\n".join(vars)).strip()

        elif shell == "bash":
            name = "bash_comp"
            template = cls._TEMPLATE_BASH
            config_path = USER_HOME + "/.bashrc"

            def gen_completion():
                return " ".join(GitProcessor.Git_Options.keys())

        complete_content = gen_completion()
        script_src = template % (complete_content)

        return name, script_src, config_path

    @classmethod
    def write_completion(cls, name, src):
        """Save completion to config path.

        Args:
            name (str): completion name.
            src (str): completion source.

        Returns:
            (str): completion full path.
        """

        path = cls.ensure_config_path(name)
        try:
            with open(path, "w") as f:
                for line in src:
                    f.write(line)
            return path
        except Exception as e:
            leave(EXIT_ERROR, "Write completion error: {}".format(e))

    @staticmethod
    def inject_into_shell(file_path, config_path):
        """Try using completion script.

        Inject the load of completion script into the configuration of shell.
        If it exists in the configuration, the injection will not be repeated.

        Args:
            file_path (str): completion file full path.
            config_path (str): shell configuration path.
        """
        try:
            with open(config_path) as f:
                shell_conf = f.read()
                _re = re.compile(r"\/\.config\/pygittools/([^\s]+)")
                files = _re.findall(shell_conf)
        except Exception as e:
            leave(EXIT_ERROR, "Read shell config error: {}".format(e))

        file_name = file_path.split("/")[-1]
        has_injected = False
        if files:
            for file in files:
                if file == file_name:
                    has_injected = True
        Log.debug("has_injected: {}".format(has_injected))

        if not has_injected:
            try:
                run_cmd('echo "source %s" >> %s ' % (file_path, config_path))
            except Exception as e:
                leave(EXIT_ERROR, "Inject error: {}".format(e))
            okay("\nPlease run: source {}".format(config_path))
        else:
            warn("This configuration already exists. {}".format(Icon_Sorry))

    @classmethod
    def complete_and_use(cls):
        """Add completion prompt script."""

        echo("\nTry to add completion ...")

        current_shell = cls.get_current_shell()
        echo("Detected shell: %s" % current_shell)

        if current_shell in cls.Supported_Shell:
            name, completion_src, config_path = cls.generate_resource(current_shell)
            file_path = cls.write_completion(name, completion_src)
            cls.inject_into_shell(file_path, config_path)
        else:
            warn("Don't support completion of %s" % current_shell)


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
                        err(line)
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
            err("Error reading configuration file.")
    else:
        err("This directory is not a git repository yet.")


def repository_info():
    """Print some information of the repository.

    repository: `Repository_Path`
    remote: read from '.git/conf'
    >>> all_branch = run_cmd_with_resp('git branch --all --color')
    >>> lastest_log = run_cmd_with_resp('git log -1')
    """

    echo("waiting ...", nl=False)

    error_str = CommandColor.Red + "Error getting" + Fx.reset
    # Get remote url.
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

    # Get all branches.
    err, res = exec_cmd("git branch --all --color")
    if err:
        branches = "\t" + error_str
    else:
        branches = textwrap.indent(res, "\t")

    # Get the lastest log.
    err, res = exec_cmd("git log --stat --oneline --decorate -1 --color")
    if err:
        git_log = "\t" + error_str
    else:
        # git_log = "\n".join(["\t" + x for x in res.strip().split("\n")])
        git_log = textwrap.indent(res, "\t")

    # Get git summary.
    err, res = exec_cmd("git shortlog --summary --numbered")
    if err:
        summary = "\t" + error_str
    else:
        summary = textwrap.indent(res, "\t")

    echo("\r[%s]        \n" % (Fx.b + "Repository Information" + Fx.reset,))
    if CONFIG.show_path:
        echo(
            "Repository: \n\t%s\n"
            % (CommandColor.SkyBlue + Repository_Path + Fx.reset,)
        )
    if CONFIG.show_remote:
        echo("Remote: \n%s\n" % remote)
    if CONFIG.show_branchs:
        echo("Branches: \n%s\n" % branches)
    if CONFIG.show_lastest_log:
        echo("Lastest log:\n%s\n" % git_log)
    if CONFIG.show_summary:
        echo("Summary:\n%s\n" % summary)


class CodeCounter(object):
    """Class of statistical code.

    Attributes:
        Absolute_Rules (dict): Precompiled rules.
        Rules (dict): The dictionary for saving filtering rules.
            >>> one_rule = {
            ...     'pattern': re.compile(r''),
            ...     'include': False
            ... }
        File_Type (dict): Supported file suffix dictionary.
        Level_Color (list): Color list. The levels are calibrated by
            subscript, and the codes of different levels are colored
            when the results are output.
        Result_Saved_Path (str): Directory to save and load results.
    """

    Absolute_Rules = [
        # Exclude `.git` folder.
        {"pattern": re.compile(r"\.git$|\.git\/"), "include": False},
        {
            # Exclude all picture formats.
            "pattern": re.compile(
                r"\.xbm$|\.tif$|\.pjp$|\.svgz$|\.jpg$|\.jpeg$|\.ico$|\.icns$|\.tiff$|\.gif$|\.svg$|\.jfif$|\.webp$|\.png$|\.bmp$|\.jpeg$|\.avif$",
                re.I,
            ),
            "include": False,
        },
        {
            # Exclude all video formats.
            "pattern": re.compile(
                r"\.avi$|\.rmvb$|\.rm$|\.asf$|\.divx$|\.mpg$|\.mpeg$|\.mpe$|\.wmv$|\.mp4$|\.mkv$|\.vob$",
                re.I,
            ),
            "include": False,
        },
        {
            # Exclude all audio frequency formats.
            "pattern": re.compile(
                r"\.mp3$|\.wma$|\.mid[i]?$|\.mpeg$|\.cda$|\.wav$|\.ape$|\.flac$|\.aiff$|\.au$",
                re.I,
            ),
            "include": False,
        },
        {
            # Exclude all font formats.
            "pattern": re.compile(
                r"\.otf$|\.woff$|\.woff2$|\.ttf$|\.eot$",
                re.I,
            ),
            "include": False,
        },
    ]

    Rules = []

    File_Types = {
        "": "",
        "c": "C",
        "conf": "Properties",
        "cfg": "Properties",
        "hpp": "C++",
        "cpp": "C++",
        "cs": "C#",
        "css": "CSS",
        "bat": "Batch",
        "dart": "Dart",
        "go": "Go",
        "gradle": "Groovy",
        "h": "C",
        "htm": "HTML",
        "html": "HTML",
        "java": "Java",
        "js": "Java Script",
        "jsx": "React",
        "json": "Json",
        "kt": "Kotlin",
        "less": "CSS",
        "lua": "Lua",
        "md": "Markdown",
        "markdown": "Markdown",
        "php": "PHP",
        "py": "Python",
        "plist": "XML",
        "properties": "Propertie",
        "ts": "Type Script",
        "tsx": "React",
        "rst": "reStructuredText",
        "sass": "CSS",
        "scss": "CSS",
        "sh": "Shell",
        "swift": "Swift",
        "vue": "Vue",
        "vim": "Vim Scirpt",
        "xml": "XML",
        "yaml": "YAML",
        "yml": "YAML",
        "zsh": "Shell",
        "dea": "XML",
        "urdf": "XML",
        "launch": "XML",
        "rb": "Ruby",
        "rs": "Rust",
        "rviz": "YAML",
        "srdf": "YAML",
        "msg": "ROS Message",
        "srv": "ROS Message",
    }

    Level_Color = [
        "",
        CommandColor.Yellow,
        CommandColor.Red,
        CommandColor.MediumVioletRed,
        CommandColor.SkyBlue,
    ]

    Result_Saved_Path = TOOLS_HOME + "/Counter"

    # Max_Thread = 10
    # Current_Thread = 0
    # Thread_Lock = threading.Lock()

    @classmethod
    def process_gitignore(cls, root, files):
        """Process `.gitignore` files and add matching rules.

        Args:
            root (str): Absolute or relative path to the directory.
            files (list): The list of all file names under the `root` path.
        """

        root = root.replace("\\", "/")
        if ".gitignore" in files:
            try:
                ignore_path = os.path.join(root, ".gitignore")
                with open(ignore_path) as f:
                    ignore_content = filter(
                        # Filter out comment lines.
                        lambda x: x and not x.startswith("#"),
                        map(
                            # Filter out white space lines.
                            # Replace `\` to `/` for windows.
                            lambda x: x.strip().replace("\\", "/"),
                            # Read the file and split the lines.
                            f.read().split("\n"),
                        ),
                    )

                    for item in ignore_content:
                        is_negative = item[0] == "!"
                        if is_negative:
                            item = item[1:]

                        slash_index = item.find("/")
                        if slash_index == 0:
                            item = root + item
                        elif slash_index == -1 or slash_index == len(item) - 1:
                            item = "/".join([root, "**", item])
                        else:
                            item = "/".join([root, item])

                        item = re.sub(
                            r"([\{\}\(\)\+\.\^\$\|])", r"\1", item
                        )  # escape char
                        item = re.sub(r"(^|[^\\])\?", ".", item)
                        item = re.sub(r"\/\*\*", "([\\\\/][^\\\\/]+)?", item)  # /**
                        item = re.sub(r"\*\*\/", "([^\\\\/]+[\\\\/])?", item)  # **/
                        item = re.sub(r"\*", "([^\\\\/]+)", item)  # for `*`
                        item = re.sub(r"\?", "*", item)  # for `?``
                        item = re.sub(r"([^\/])$", r"\1(([\\\\/].*)|$)", item)
                        item = re.sub(
                            r"\/$", "(([\\\\/].*)|$)", item
                        )  # for trialing with `/`
                        cls.Rules.append(
                            {"pattern": re.compile(item), "include": is_negative}
                        )
            except PermissionError:
                if confirm(
                    "Can't read {}, wether get jurisdiction[y/n]:".format(ignore_path)
                ):
                    os.chmod(ignore_path, stat.S_IXGRP)
                    os.chmod(ignore_path, stat.S_IWGRP)
                    cls.process_gitignore(root, files)
            except Exception as e:
                print("Read gitignore error: {}".format(e))

    @classmethod
    def matching(cls, full_path):
        """Matching rules.

        Judge whether it is the required file according to the rule matching path.
        Returns `True` if the file not needs to be ignored, or `False` if needs.

        Args:
            full_path (str): File full path for matching.
        """

        # Precompiled rules have the highest priority.
        if list(
            filter(lambda rule: rule["pattern"].search(full_path), cls.Absolute_Rules)
        ):
            return False

        # Matching the generated rules.
        res = list(filter(lambda rule: rule["pattern"].search(full_path), cls.Rules))
        if not res:
            return True
        else:
            # If multiple rules match successfully, we think the last rule added has
            # the highest priority. Or if just one, this no problem also.
            return res[-1]["include"]
            # selected_rule = max(res, key=lambda rule: len(str(rule["pattern"])))

    # @staticmethod
    # def count_file_thread(full_path):
    #     pass

    @staticmethod
    def _count_err_callback(e):
        """Handle of processing walk error."""
        print("Walk error: {}".format(e))
        raise SystemExit(0)

    @classmethod
    def count(cls, root_path=".", use_ignore=True, progress=True):
        """Statistics file and returns the result dictionary.

        Args:
            root_path (str): The path is walk needed.
            use_ignore (bool): Wether ignore files in `.gitignore`. Defaults to True.
            progress (bool): Wether show processing. Defaults to True.

        Return:
            result (dict): Dictionary containing statistical results.
            >>> result = {
            ...     'py': {
            ...         'files': 5,
            ...         'lines': 2124,
            ...     }
            ... }
            >>> CodeCounter.count('~/.config', use_ignore=True)
        """

        use_ignore = CONFIG.use_gitignore
        if progress:
            import shutil

            width = shutil.get_terminal_size().columns
            if width > 55:
                _msg = "\rValid files found: {:,}, Invalid files found: {:,}"
            else:
                _msg = "\r:: [{:,} | {:,}]"

        result = {}
        valid_counter = 0
        invalid_counter = 0
        invalid_list = []
        for root, _, files in os.walk(
            root_path,
            onerror=cls._count_err_callback,
        ):

            # First judge whether the directory is valid. Invalid directories
            # do not traverse files.
            is_effective_dir = cls.matching(root)
            if not is_effective_dir:
                continue

            if use_ignore:
                cls.process_gitignore(root, files)

            for file in files:
                full_path = os.path.join(root, file)
                is_effective = cls.matching(full_path)
                if is_effective:
                    # TODO: the way of process file type not good.
                    suffix = file.split(".")[-1]
                    suffix = cls.File_Types.get(suffix.lower(), suffix)
                    # TODO: counter, may need use threading.
                    try:
                        with open(full_path) as f:
                            count = len(f.read().split("\n"))

                        # Superposition.
                        if result.get(suffix, None) is None:
                            result[suffix] = {"files": 1, "lines": count}
                        else:
                            result[suffix]["files"] += 1
                            result[suffix]["lines"] += count
                        valid_counter += 1
                    except Exception as e:
                        invalid_counter += 1
                        invalid_list.append(file)
                        continue
                    finally:
                        if progress:
                            echo(
                                _msg.format(valid_counter, invalid_counter),
                                nl=False,
                            )

        # from pprint import pprint

        # pprint(cls.rules)
        if progress:
            echo("")
        return result, invalid_list

    @staticmethod
    def recorded_result(root_path):
        """Load count result."""
        file_name = root_path.replace("/", "_").replace("\\", "_").replace(".", "_")
        file_path = os.path.join(CodeCounter.Result_Saved_Path, file_name)
        try:
            with open(file_path) as rf:
                res = json.load(rf)
                return res
        except Exception:
            return None

    @staticmethod
    def save_result(result, root_path):
        """Save count result.

        Generate name according to `root_path`, then try save the record
        result to [`TOOLS_HOME`/Counter].

        Args:
            result (dict): Statistical results.
            root_path (str): Traversal directory.

        Return:
            (bool): Wether saving successful.
        """

        file_name = root_path.replace("/", "_").replace("\\", "_").replace(".", "_")
        file_path = os.path.join(CodeCounter.Result_Saved_Path, file_name)
        ensure_path(CodeCounter.Result_Saved_Path)
        try:
            with open(file_path, "w") as wf:
                json.dump(result, wf, indent=2)
                return True
        except Exception:
            return False

    @classmethod
    def color_index(cls, _count):
        _index = len(str(_count // 1000))
        if _index > len(cls.Level_Color):
            return -1
        else:
            return _index - 1

    @classmethod
    def format_print(cls, new, old=None):
        """Print result with color and diff.

        If the console width is not enough, the output is simple.

        Args:
            new (dict): Current statistical results.
            old (dict|None): The results saved in the past may not exist.
        """

        needed_width = 67
        import shutil

        width = shutil.get_terminal_size().columns
        if CONFIG.result_format == "simple" or width < needed_width:
            for key, value in new.items():
                line = "{}: {:,} | {:,}".format(key, value["files"], value["lines"])
                echo(line)
            return

        elif CONFIG.result_format == "table":
            # Print full time.
            echo(time.strftime("%H:%M:%S %a %Y-%m-%d %Z", time.localtime()))
            # Print title.
            echo("{}{:^67}{}".format(Fx.bold, "[Code Counter Result]", Fx.unbold))
            # Print table header.
            echo("=" * needed_width)
            echo(
                "| {bold}{:<21}{unbold}| {bold}{:<17}{unbold}| {bold}{:<22}{unbold}|".format(
                    "Language", "Files", "Code lines", bold=Fx.bold, unbold=Fx.unbold
                )
            )
            echo("|{sep:-<22}|{sep:-<18}|{sep:-<23}|".format(sep="-"))
            # Print table content.
            sum = 0
            additions = 0
            deletions = 0
            for key, value in new.items():
                # Processing too long name.
                key = shorten(key, 20, front=True)

                # Set color.
                lines_color = cls.Level_Color[cls.color_index(value["lines"])]

                # Compare change.
                if isinstance(old, dict) and old.get(key, None) is not None:
                    old_files = old.get(key).get("files", None)
                    old_lines = old.get(key).get("lines", None)

                    if old_files and old_files != value["files"]:
                        files_change = "{:+}".format(value["files"] - old_files)
                        files_symbol = files_change[0]
                    else:
                        files_symbol = files_change = ""

                    if old_lines and old_lines != value["lines"]:
                        _change = value["lines"] - old_lines
                        lines_change = "{:+}".format(_change)
                        lines_symbol = lines_change[0]
                        if _change > 0:
                            additions += _change
                        else:
                            deletions -= _change
                    else:
                        lines_symbol = lines_change = ""

                else:
                    files_change = files_symbol = lines_change = lines_symbol = ""

                print(
                    (
                        "| {:<21}"
                        "| {file_style}{:<11,}{reset} {file_change_style}{file_change:>5}{reset}"
                        "| {lines_style}{:<15,}{reset} {line_change_style}{line_change:>6}{reset}|"
                    ).format(
                        key,
                        value["files"],
                        value["lines"],
                        file_style=Fx.italic,
                        file_change_style=CommandColor.Symbol.get(files_symbol, ""),
                        file_change=files_change,
                        lines_style=lines_color,
                        line_change_style=CommandColor.Symbol.get(lines_symbol, ""),
                        line_change=lines_change,
                        reset=Fx.reset,
                    )
                )
                sum += value["lines"]
            echo("-" * needed_width)
            # Print total and change graph.
            echo(" Total: {}".format(sum))
            if additions > 0 or deletions > 0:
                echo(" Altered: ", nl=False)
                echo("+" * ceil(additions / 10), color=CommandColor.Green, nl=False)
                echo("-" * ceil(deletions / 10), color=CommandColor.Red)

    @classmethod
    def count_and_format_print(
        cls, root_path=os.getcwd(), use_ignore=True, if_save=True
    ):
        result, invalid_list = cls.count(root_path, use_ignore)
        old_result = cls.recorded_result(root_path)
        # diff print.
        cls.format_print(result, old_result)
        if if_save:
            cls.save_result(result, root_path)
        if (
            CONFIG.show_invalid
            and invalid_list
            and confirm("Wether print invalid file list?[y/n]", default=False)
        ):
            print(invalid_list)


class GitignoreGenetor(object):
    """Generate gitignore template.

    Attributes:
        Genres (dict): supported type.

    Raises:
        SystemExit: Can't get template.
        SystemExit: No name.
    """

    # Supported type.
    Genres = {
        "android": "Android",
        "c++": "C++",
        "cpp": "C++",
        "c": "C",
        "dart": "Dart",
        "elisp": "Elisp",
        "gitbook": "GitBook",
        "go": "Go",
        "java": "Java",
        "kotlin": "Java",
        "lua": "Lua",
        "maven": "Maven",
        "node": "Node",
        "python": "Python",
        "qt": "Qt",
        "r": "R",
        "ros": "ROS",
        "ruby": "Ruby",
        "rust": "Rust",
        "sass": "Sass",
        "swift": "Swift",
        "unity": "Unity",
    }

    @staticmethod
    def parse_gitignore(content):
        """Parse html for getting gitignore content.

        Args:
            content (str): template page html.

        Returns:
            (str): gitignore template content.
        """

        text = re.findall(r"(<table.*?>.*?<\/table>)", content, re.S)
        if not text:
            return ""

        content_re = re.compile(r"<\/?\w+.*?>", re.S)
        res = content_re.sub("", text[0])
        res = re.sub(r"(\n[^\S\r\n]+)+", "\n", res)
        return res

    @staticmethod
    def get_ignore_from_url(url):
        """Crawl gitignore template.

        Args:
            url (str): gitignore template url.

        Raises:
            SystemExit: Failed to get web page.

        Returns:
            (str): html string.
        """

        try:
            timeout = CONFIG.timeout
            handle = urlopen(url, timeout=timeout)
        except Exception:
            err("Failed to get content and will exit.")
            raise SystemExit(0)

        content = handle.read().decode("utf-8")

        return content

    @classmethod
    def create_gitignore(cls, genre):
        """Try to create gitignore template file.

        Args:
            genre (str): template type, like: 'python'.
        """

        name = cls.Genres.get(genre.lower(), None)
        if name is None:
            err("Unsupported type: %s" % genre)
            echo("Supported type: %s.  Case insensitive." % " ".join(cls.Genres.keys()))
            raise SystemExit(0)

        ignore_path = Repository_Path + "/.gitignore"
        whether_write = True
        if os.path.exists(ignore_path):
            echo(
                "`.gitignore` existed, overwrite this file? (default: y) [y/n]:",
                nl=False,
            )
            whether_write = confirm()
        if whether_write:
            base_url = "https://github.com/github/gitignore/blob/master/%s.gitignore"

            target_url = base_url % name
            echo(
                "Will get ignore file content from %s"
                % (Fx.italic + Fx.underline + target_url + Fx.reset)
            )
            content = cls.get_ignore_from_url(target_url)
            ignore_content = cls.parse_gitignore(content)

            echo("Got content, trying to write ... ")
            try:
                with open(ignore_path, "w") as f:
                    f.write(ignore_content)
                echo("Write gitignore file successful. {}".format(Icon_Smiler))
            except Exception:
                err("Write gitignore file failed.")
                echo("You can replace it with the following:")
                echo("#" * 60)
                echo(ignore_content)


def introduce():
    """Print the description information."""

    # Print tools version and path.
    echo("[%s] version: %s" % (__project__, __version__), style=Fx.b)

    # Print git version.
    if Git_Version is None:
        warn("Don't found Git, maybe need install.")
    else:
        echo(Git_Version)

    # Print package path.
    echo("Path: ", style=Fx.b, nl=False)
    echo("%s\n" % __file__, color=CommandColor.SkyBlue, style=Fx.underline)

    echo("Description:", style=Fx.b)
    echo(
        (
            "  Terminal tool, help you use git more simple."
            " Support Linux and MacOS.\n"
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
        width = CONFIG.line_width
        import shutil

        max_width = shutil.get_terminal_size().columns
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
        if CONFIG.use_color:
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
        return "".join(indent + line for line in text.splitlines(keepends=True))

    def _get_help_string(self, action):
        help = action.help
        if "%(default)" not in action.help:
            if action.default is not argparse.SUPPRESS:
                defaulting_nargs = [argparse.OPTIONAL, argparse.ZERO_OR_MORE]
                if action.option_strings or action.nargs in defaulting_nargs:
                    # help += " (default: %(default)s)"
                    pass
        return help


@time_testing
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
        % ", ".join(GitignoreGenetor.Genres.keys()),
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
    args.add_argument(
        "command", nargs="?", default="|", type=str, help="Short git command."
    )
    args.add_argument("args", nargs="*", type=str, help="Command parameter list.")
    stdargs = args.parse_args()

    if custom_commands is not None:
        stdargs = args.parse_args(custom_commands)
    # print(stdargs)

    # Setup log handle.
    LogHandle.setup_logging(
        debug=stdargs.debug,
        log_file=None if stdargs.out_log else TOOLS_HOME + "/log/gittools.log",
    )

    if stdargs.complete:
        Completion.complete_and_use()
        raise SystemExit(0)

    if stdargs.show_commands:
        GitProcessor.command_help()
        raise SystemExit(0)

    if stdargs.command_type:
        GitProcessor.command_help_by_type(stdargs.command_type)
        raise SystemExit(0)

    if stdargs.types:
        GitProcessor.type_help()
        raise SystemExit(0)

    if stdargs.config:
        git_local_config()
        raise SystemExit(0)

    if stdargs.information:
        repository_info()
        raise SystemExit(0)

    if stdargs.ignore_type:
        GitignoreGenetor.create_gitignore(stdargs.ignore_type)
        raise SystemExit(0)

    if stdargs.create_config:
        Config.create_config_template()
        raise SystemExit(0)

    if stdargs.count:
        path = stdargs.count if stdargs.count != "." else os.getcwd()
        CodeCounter.count_and_format_print(root_path=path)
        raise SystemExit(0)

    if stdargs.command:
        if stdargs.command == "|":
            introduce()
        else:
            command = stdargs.command
            GitProcessor.process_command(command, stdargs.args)


if __name__ == "__main__":
    command_g()
