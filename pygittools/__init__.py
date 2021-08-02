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
__license__ = "MIT"
__version__ = "1.0.4-beta.1"
__author__ = "Zachary Zhang"
__email__ = "zlj19971222@outlook.com"
__git_url__ = "https://github.com/zlj-zz/pygittools.git"


import os
import re
import sys
import subprocess
import signal
import argparse
import logging
import logging.handlers
import time
import random
import json
import threading
from math import sqrt, ceil, exp
from collections import Counter
from functools import wraps


#####################################################################
# Part of compatibility.                                            #
# Handled the incompatibility between python2 and python3.          #
#####################################################################
PYTHON3 = sys.version_info > (3, 0)
if PYTHON3:
    input = input

    import urllib.request

    urlopen = urllib.request.urlopen
else:
    input = raw_input

    import urllib2

    urlopen = urllib2.urlopen


#####################################################################
# Part of Utils.                                                    #
# Some tools and methods for global use. Also contains some special #
# global variables (readonly).                                      #
#####################################################################
USER_HOME = os.environ["HOME"]
TOOLS_HOME = USER_HOME + "/.config/pygittools"
Log = logging.getLogger(__name__)


def ensure_path(dir_path):
    """Determine whether the file path exists. If not, create a directory.
    Args:
        dir_path: (str), like: "~/.config/xxx"
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


class LogHandle(object):
    """Set log handle.
    Attributes:
        FMT_NORMAL: Log style in normal mode.
        FMT_DEBUG: Log style in debug mode.

    Methods:
        setup_logging: setup log handle setting.
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


def exit_(*args):
    """Exit program.

    Receive error code, error message. If the error code matches, print the
    error information to the log. Then the command line output prompt, and
    finally exit.

    Args:
        *args:
            code: Exit code.
            msg: Error message.
    """
    if args and args[0] == EXIT_ERROR:
        Log.error(args[1:])
        print("Please check {}".format(TOOLS_HOME))

    raise SystemExit(0)


def run_cmd(*args):
    """
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


def run_cmd_with_resp(*args):
    """
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

    Return: (bool)

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
        _, git_version_ = run_cmd_with_resp("git --version")
        if git_version_:
            return git_version_
        else:
            return None
    except Exception:
        Log.warning("Can not found Git in environment.")
        return None


Git_Version = git_version()


def current_repository():
    """Get the current git repository path. If not, the path is empty."""
    err, path = run_cmd_with_resp("git rev-parse --git-dir")

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
    echo("%s%s%s%s" % (Fx.b, CommandColor.Green, msg, Fx.reset), nl=nl)


def warn(msg, nl=True):
    """Print yellow information."""
    echo("%s%s%s%s" % (Fx.b, CommandColor.Gold, msg, Fx.reset), nl=nl)


def err(msg, nl=True):
    """Print red information."""
    echo("%s%s%s%s" % (Fx.b, CommandColor.Red, msg, Fx.reset), nl=nl)


#####################################################################
# Part of command.                                                  #
#####################################################################
class GitOptionState:
    # command type.
    String = 1
    Func = 1 << 2
    # Accept parameters.
    No = 1 << 3
    Multi = 1 << 4


def add(args):
    args_str = " ."
    if args:
        args_str = " ".join(args)

    echo("🌈  Storage file: {}".format("all" if args_str.strip() == "." else args_str))
    run_cmd("git add " + args_str)


def fetch_remote_branch(args):
    branch = args[0] if len(args) > 1 else None

    if branch:
        run_cmd("git fetch origin {}:{} ".format(branch, branch))
    else:
        err("This option need a branch name.")


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
    email_re = re.compile(r"^[0-9a-zA-Z_]{0,19}@[0-9a-zA-Z]{1,13}\.[com,cn,net]{1,3}$")
    while True:
        if email_re.match(email) is None:
            err("Bad mailbox format.")
            email = input("Please input email again:")
        else:
            break

    if run_cmd(GIT_OPTIONS["user"]["command"] + other + name) and run_cmd(
        GIT_OPTIONS["email"]["command"] + other + email
    ):
        okay("Successfully set.")
    else:
        err("Failed. Please check log.")


TYPES = [
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

# Global command dictionary, including attributes:
#     command type,
#     complete command,
#     help information
GIT_OPTIONS = {
    # Branch
    "b": {
        "state": GitOptionState.String | GitOptionState.Multi,
        "command": "git branch ",
        "help-msg": "lists, creates, renames, and deletes branches.",
    },
    "bc": {
        "state": GitOptionState.String | GitOptionState.Multi,
        "command": "git checkout -b ",
        "help-msg": "creates a new branch.",
    },
    "bl": {
        "state": GitOptionState.String | GitOptionState.No,
        "command": "git branch -vv ",
        "help-msg": "lists branches and their commits.",
    },
    "bL": {
        "state": GitOptionState.String | GitOptionState.No,
        "command": "git branch --all -vv ",
        "help-msg": "lists local and remote branches and their commits.",
    },
    "bs": {
        "state": GitOptionState.String | GitOptionState.No,
        "command": "git show-branch ",
        "help-msg": "lists branches and their commits with ancestry graphs.",
    },
    "bS": {
        "state": GitOptionState.String | GitOptionState.No,
        "command": "git show-branch --all ",
        "help-msg": "lists local and remote branches and their commits with ancestry graphs.",
    },
    "bm": {
        "state": GitOptionState.String | GitOptionState.Multi,
        "command": "git branch --move ",
        "help-msg": "renames a branch.",
    },
    "bM": {
        "state": GitOptionState.String | GitOptionState.Multi,
        "command": "git branch --move --force ",
        "help-msg": "renames a branch even if the new branch name already exists.",
    },
    # Commit
    "c": {
        "state": GitOptionState.String | GitOptionState.No,
        "command": "git commit --verbose ",
        "help-msg": "records changes to the repository.",
    },
    "ca": {
        "state": GitOptionState.String | GitOptionState.No,
        "command": "git commit --verbose --all ",
        "help-msg": "commits all modified and deleted files.",
    },
    "cA": {
        "state": GitOptionState.String | GitOptionState.No,
        "command": "git commit --verbose --patch ",
        "help-msg": "commits all modified and deleted files interactively",
    },
    "cm": {
        "state": GitOptionState.String | GitOptionState.No,
        "command": "git commit --verbose --message ",
        "help-msg": "commits with the given message.",
    },
    "co": {
        "state": GitOptionState.String | GitOptionState.Multi,
        "command": "git checkout ",
        "help-msg": "checks out a branch or paths to the working tree.",
    },
    "cO": {
        "state": GitOptionState.String | GitOptionState.Multi,
        "command": "git checkout --patch ",
        "help-msg": "checks out hunks from the index or the tree interactively.",
    },
    "cf": {
        "state": GitOptionState.String | GitOptionState.No,
        "command": "git commit --amend --reuse-message HEAD ",
        "help-msg": "amends the tip of the current branch reusing the same log message as HEAD.",
    },
    "cF": {
        "state": GitOptionState.String | GitOptionState.No,
        "command": "git commit --verbose --amend ",
        "help-msg": "amends the tip of the current branch.",
    },
    "cr": {
        "state": GitOptionState.String | GitOptionState.Multi,
        "command": "git revert ",
        "help-msg": "reverts existing commits by reverting patches and recording new commits.",
    },
    "cR": {
        "state": GitOptionState.String | GitOptionState.No,
        "command": 'git reset "HEAD^" ',
        "help-msg": "removes the HEAD commit.",
    },
    "cs": {
        "state": GitOptionState.String | GitOptionState.Multi,
        "command": 'git show --pretty=format:"%C(bold yellow)commit %H%C(auto)%d%n%C(bold)Author: %C(blue)%an <%ae> %C(reset)%C(cyan)%ai (%ar)%n%C(bold)Commit: %C(blue)%cn <%ce> %C(reset)%C(cyan)%ci (%cr)%C(reset)%n%+B"',
        "help-msg": "shows one or more objects (blobs, trees, tags and commits).",
    },
    # Conflict(C)
    "Cl": {
        "state": GitOptionState.String | GitOptionState.No,
        "command": "git --no-pager diff --diff-filter=U --name-only ",
        "help-msg": "lists unmerged files.",
    },
    "Ca": {
        "state": GitOptionState.String | GitOptionState.Multi,
        "command": "git add git --no-pager diff --diff-filter=U --name-only ",
        "help-msg": "adds unmerged file contents to the index.",
    },
    "Ce": {
        "state": GitOptionState.String | GitOptionState.Multi,
        "command": "git mergetool git --no-pager diff --diff-filter=U --name-only ",
        "help-msg": "executes merge-tool on all unmerged files.",
    },
    "Co": {
        "state": GitOptionState.String | GitOptionState.Multi,
        "command": "git checkout --ours -- ",
        "help-msg": "checks out our changes for unmerged paths.",
    },
    "CO": {
        "state": GitOptionState.String | GitOptionState.No,
        "command": "git checkout --ours -- git --no-pager diff --diff-filter=U --name-only ",
        "help-msg": "checks out our changes for all unmerged paths.",
    },
    "Ct": {
        "state": GitOptionState.String | GitOptionState.Multi,
        "command": "git checkout --theirs -- ",
        "help-msg": "checks out their changes for unmerged paths.",
    },
    "CT": {
        "state": GitOptionState.String | GitOptionState.No,
        "command": "git checkout --theirs -- git --no-pager diff --diff-filter=U --name-only ",
        "help-msg": "checks out their changes for all unmerged paths.",
    },
    # Fetch(f)
    "f": {
        "state": GitOptionState.String | GitOptionState.Multi,
        "command": "git fetch ",
        "help-msg": "downloads objects and references from another repository.",
    },
    "fc": {
        "state": GitOptionState.String | GitOptionState.Multi,
        "command": "git clone ",
        "help-msg": "clones a repository into a new directory.",
    },
    "fC": {
        "state": GitOptionState.String | GitOptionState.Multi,
        "command": "git clone --depth=1 ",
        "help-msg": "clones a repository into a new directory clearly(depth:1).",
    },
    "fm": {
        "state": GitOptionState.String | GitOptionState.Multi,
        "command": "git pull ",
        "help-msg": "fetches from and merges with another repository or local branch.",
    },
    "fr": {
        "state": GitOptionState.String | GitOptionState.Multi,
        "command": "git pull --rebase ",
        "help-msg": "fetches from and rebase on top of another repository or local branch.",
    },
    "fu": {
        "state": GitOptionState.String | GitOptionState.Multi,
        "command": "git fetch --all --prune && git merge --ff-only @{u} ",
        "help-msg": "removes un-existing remote-tracking references, fetches all remotes and merges.",
    },
    "fb": {
        "state": GitOptionState.Func | GitOptionState.No,
        "command": fetch_remote_branch,
        "help-msg": "fetch other branch to local as same name.",
    },
    # Index(i)
    "ia": {
        "state": GitOptionState.Func | GitOptionState.Multi,
        "command": add,
        "help-msg": "adds file contents to the index(default: all files).",
    },
    "iA": {
        "state": GitOptionState.String | GitOptionState.Multi,
        "command": "git add --patch ",
        "help-msg": "adds file contents to the index interactively.",
    },
    "iu": {
        "state": GitOptionState.String | GitOptionState.Multi,
        "command": "git add --update ",
        "help-msg": "adds file contents to the index (updates only known files).",
    },
    "id": {
        "state": GitOptionState.String | GitOptionState.Multi,
        "command": "git diff --no-ext-diff --cached ",
        "help-msg": "displays changes between the index and a named commit (diff).",
    },
    "iD": {
        "state": GitOptionState.String | GitOptionState.Multi,
        "command": "git diff --no-ext-diff --cached --word-diff ",
        "help-msg": "displays changes between the index and a named commit (word diff).",
    },
    "ir": {
        "state": GitOptionState.String | GitOptionState.Multi,
        "command": "git reset ",
        "help-msg": "resets the current HEAD to the specified state.",
    },
    "iR": {
        "state": GitOptionState.String | GitOptionState.Multi,
        "command": "git reset --patch ",
        "help-msg": "resets the current index interactively.",
    },
    "ix": {
        "state": GitOptionState.String | GitOptionState.Multi,
        "command": "git rm --cached -r ",
        "help-msg": "removes files from the index (recursively).",
    },
    "iX": {
        "state": GitOptionState.String | GitOptionState.Multi,
        "command": "git rm --cached -rf ",
        "help-msg": "removes files from the index (recursively and forced).",
    },
    # Log(l)
    "l": {
        "state": GitOptionState.String | GitOptionState.Multi,
        "command": "git log --graph --all --decorate ",
        "help-msg": "displays the log with good format.",
    },
    "l1": {
        "state": GitOptionState.String | GitOptionState.Multi,
        "command": "git log --graph --all --decorate --oneline ",
        "help-msg": "",
    },
    "ls": {
        "state": GitOptionState.String | GitOptionState.No,
        "command": 'git log --topo-order --stat --pretty=format:"%C(bold yellow)commit %H%C(auto)%d%n%C(bold)Author: %C(blue)%an <%ae> %C(reset)%C(cyan)%ai (%ar)%n%C(bold)Commit: %C(blue)%cn <%ce> %C(reset)%C(cyan)%ci (%cr)%C(reset)%n%+B" ',
        "help-msg": "displays the stats log.",
    },
    "ld": {
        "state": GitOptionState.String | GitOptionState.No,
        "command": 'git log --topo-order --stat --patch --pretty=format:"%C(bold yellow)commit %H%C(auto)%d%n%C(bold)Author: %C(blue)%an <%ae> %C(reset)%C(cyan)%ai (%ar)%n%C(bold)Commit: %C(blue)%cn <%ce> %C(reset)%C(cyan)%ci (%cr)%C(reset)%n%+B" ',
        "help-msg": "displays the diff log.",
    },
    "lv": {
        "state": GitOptionState.String | GitOptionState.No,
        "command": 'git log --topo-order --show-signature --pretty=format:"%C(bold yellow)commit %H%C(auto)%d%n%C(bold)Author: %C(blue)%an <%ae> %C(reset)%C(cyan)%ai (%ar)%n%C(bold)Commit: %C(blue)%cn <%ce> %C(reset)%C(cyan)%ci (%cr)%C(reset)%n%+B" ',
        "help-msg": "displays the log, verifying the GPG signature of commits.",
    },
    "lc": {
        "state": GitOptionState.String | GitOptionState.Multi,
        "command": "git shortlog --summary --numbered ",
        "help-msg": "displays the commit count for each contributor in descending order.",
    },
    "lr": {
        "state": GitOptionState.String | GitOptionState.Multi,
        "command": "git reflog ",
        "help-msg": "manages reflog information.",
    },
    # Merge(m)
    "m": {
        "state": GitOptionState.String | GitOptionState.Multi,
        "command": "git merge ",
        "help-msg": "joins two or more development histories together.",
    },
    "ma": {
        "state": GitOptionState.String | GitOptionState.Multi,
        "command": "git merge --abort ",
        "help-msg": "aborts the conflict resolution, and reconstructs the pre-merge state.",
    },
    "mC": {
        "state": GitOptionState.String | GitOptionState.Multi,
        "command": "git merge --no-commit ",
        "help-msg": "performs the merge but does not commit.",
    },
    "mF": {
        "state": GitOptionState.String | GitOptionState.Multi,
        "command": "git merge --no-ff ",
        "help-msg": "creates a merge commit even if the merge could be resolved as a fast-forward.",
    },
    "mS": {
        "state": GitOptionState.String | GitOptionState.Multi,
        "command": "git merge -S ",
        "help-msg": "performs the merge and GPG-signs the resulting commit.",
    },
    "mv": {
        "state": GitOptionState.String | GitOptionState.Multi,
        "command": "git merge --verify-signatures ",
        "help-msg": "verifies the GPG signature of the tip commit of the side branch being merged.",
    },
    "mt": {
        "state": GitOptionState.String | GitOptionState.Multi,
        "command": "git mergetool ",
        "help-msg": "runs the merge conflict resolution tools to resolve conflicts.",
    },
    # Push(p)
    "p": {
        "state": GitOptionState.String | GitOptionState.Multi,
        "command": "git push ",
        "help-msg": "updates remote refs along with associated objects.",
    },
    "pf": {
        "state": GitOptionState.String | GitOptionState.Multi,
        "command": "git push --force-with-lease ",
        "help-msg": 'forces a push safely (with "lease").',
    },
    "pF": {
        "state": GitOptionState.String | GitOptionState.Multi,
        "command": "git push --force ",
        "help-msg": "forces a push. ",
    },
    "pa": {
        "state": GitOptionState.String | GitOptionState.Multi,
        "command": "git push --all ",
        "help-msg": "pushes all branches.",
    },
    "pA": {
        "state": GitOptionState.String | GitOptionState.Multi,
        "command": "git push --all && git push --tags ",
        "help-msg": "pushes all branches and tags.",
    },
    "pt": {
        "state": GitOptionState.String | GitOptionState.Multi,
        "command": "git push --tags ",
        "help-msg": "pushes all tags.",
    },
    "pc": {
        "state": GitOptionState.String | GitOptionState.Multi,
        "command": 'git push --set-upstream origin "$(git symbolic-ref -q --short HEAD 2> /dev/null)" ',
        "help-msg": "pushes the current branch and adds origin as an upstream reference for it.",
    },
    "pp": {
        "state": GitOptionState.String | GitOptionState.Multi,
        "command": 'git pull origin "$(git symbolic-ref -q --short HEAD 2> /dev/null)" && git push origin "$(git symbolic-ref -q --short HEAD 2> /dev/null)" ',
        "help-msg": "pulls and pushes the current branch from origin to origin.",
    },
    # Remote(R)
    "R": {
        "state": GitOptionState.String | GitOptionState.Multi,
        "command": "git remote ",
        "help-msg": "manages tracked repositories.",
    },
    "Rl": {
        "state": GitOptionState.String | GitOptionState.Multi,
        "command": "git remote --verbose ",
        "help-msg": "lists remote names and their URLs.",
    },
    "Ra": {
        "state": GitOptionState.String | GitOptionState.Multi,
        "command": "git remote add ",
        "help-msg": "adds a new remote.",
    },
    "Rx": {
        "state": GitOptionState.String | GitOptionState.Multi,
        "command": "git remote rm ",
        "help-msg": "removes a remote.",
    },
    "Rm": {
        "state": GitOptionState.String | GitOptionState.Multi,
        "command": "git remote rename ",
        "help-msg": "renames a remote.",
    },
    "Ru": {
        "state": GitOptionState.String | GitOptionState.Multi,
        "command": "git remote update ",
        "help-msg": "fetches remotes updates.",
    },
    "Rp": {
        "state": GitOptionState.String | GitOptionState.Multi,
        "command": "git remote prune ",
        "help-msg": "prunes all stale remote tracking branches.",
    },
    "Rs": {
        "state": GitOptionState.String | GitOptionState.Multi,
        "command": "git remote show ",
        "help-msg": "shows information about a given remote.",
    },
    "RS": {
        "state": GitOptionState.String | GitOptionState.Multi,
        "command": "git remote set-url ",
        "help-msg": "changes URLs for a remote.",
    },
    # Stash(s)
    "s": {
        "state": GitOptionState.String | GitOptionState.Multi,
        "command": "git stash ",
        "help-msg": "stashes the changes of the dirty working directory.",
    },
    "sp": {
        "state": GitOptionState.String | GitOptionState.Multi,
        "command": "git stash pop ",
        "help-msg": "removes and applies a single stashed state from the stash list.",
    },
    "sl": {
        "state": GitOptionState.String | GitOptionState.Multi,
        "command": "git stash list ",
        "help-msg": "lists stashed states.",
    },
    "sd": {
        "state": GitOptionState.String | GitOptionState.Multi,
        "command": "git stash show",
        "help-msg": "",
    },
    "sD": {
        "state": GitOptionState.String | GitOptionState.Multi,
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
        "state": GitOptionState.String | GitOptionState.Multi,
        "command": "git tag ",
        "help-msg": "creates, lists, deletes or verifies a tag object signed with GPG.",
    },
    "ta": {
        "state": GitOptionState.String | GitOptionState.Multi,
        "command": "git tag -a ",
        "help-msg": "create a new tag.",
    },
    "tx": {
        "state": GitOptionState.String | GitOptionState.Multi,
        "command": "git tag --delete ",
        "help-msg": "deletes tags with given names.",
    },
    # Working tree(w)
    "ws": {
        "state": GitOptionState.String | GitOptionState.No,
        "command": "git status --short ",
        "help-msg": "displays working-tree status in the short format.",
    },
    "wS": {
        "state": GitOptionState.String | GitOptionState.Multi,
        "command": "git status ",
        "help-msg": "displays working-tree status.",
    },
    "wd": {
        "state": GitOptionState.String | GitOptionState.Multi,
        "command": "git diff --no-ext-diff ",
        "help-msg": "displays changes between the working tree and the index (diff).",
    },
    "wD": {
        "state": GitOptionState.String | GitOptionState.Multi,
        "command": "git diff --no-ext-diff --word-diff ",
        "help-msg": "displays changes between the working tree and the index (word diff).",
    },
    "wr": {
        "state": GitOptionState.String | GitOptionState.Multi,
        "command": "git reset --soft ",
        "help-msg": "resets the current HEAD to the specified state, does not touch the index nor the working tree.",
    },
    "wR": {
        "state": GitOptionState.String | GitOptionState.Multi,
        "command": "git reset --hard ",
        "help-msg": "resets the current HEAD, index and working tree to the specified state.",
    },
    "wc": {
        "state": GitOptionState.String | GitOptionState.Multi,
        "command": "git clean --dry-run ",
        "help-msg": "cleans untracked files from the working tree (dry-run).",
    },
    "wC": {
        "state": GitOptionState.String | GitOptionState.No,
        "command": "git clean -d --force ",
        "help-msg": "cleans untracked files from the working tree.",
    },
    "wm": {
        "state": GitOptionState.String | GitOptionState.Multi,
        "command": "git mv ",
        "help-msg": "moves or renames files.",
    },
    "wM": {
        "state": GitOptionState.String | GitOptionState.Multi,
        "command": "git mv -f ",
        "help-msg": "moves or renames files (forced).",
    },
    "wx": {
        "state": GitOptionState.String | GitOptionState.Multi,
        "command": "git rm -r ",
        "help-msg": "removes files from the working tree and from the index (recursively).",
    },
    "wX": {
        "state": GitOptionState.String | GitOptionState.Multi,
        "command": "git rm -rf ",
        "help-msg": "removes files from the working tree and from the index (recursively and forced).",
    },
    # Setting
    "savepd": {
        "state": GitOptionState.String | GitOptionState.Multi,
        "command": "git config credential.helper store ",
        "help-msg": "Remember your account and password.",
    },
    "ue": {
        "state": GitOptionState.Func | GitOptionState.Multi,
        "command": set_email_and_username,
        "help-msg": "set email and username interactively.",
    },
    "user": {
        "state": GitOptionState.String | GitOptionState.Multi,
        "command": "git config user.name ",
        "help-msg": "set username.",
    },
    "email": {
        "state": GitOptionState.String | GitOptionState.Multi,
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


def similar_command(command, all_commands):
    """Get the most similar command with K-NearestNeighbor.
    Args:
        command (str): command string.
        all_commands (list): The list of all command.
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


def color_command(command):
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


def process_command(c, args=None):
    """Process command and arguments."""
    if Git_Version is None:
        err("Git is not detected. Please install Git first.")
        raise SystemExit(0)

    option = GIT_OPTIONS.get(c, None)

    if option is None:
        echo("Don't support this command, please try ", nl=False)
        warn("g --show-commands")
        predicted_command = similar_command(c, GIT_OPTIONS.keys())
        echo(
            "🧐 The wanted command is %s ?"
            % (CommandColor.Green + predicted_command + Fx.reset),
            nl=False,
        )
        flag = confirm("[y/n]:")
        if flag:
            process_command(predicted_command, args=args)

        raise SystemExit(0)

    state = option.get("state", None)
    command = option.get("command", None)

    if state & GitOptionState.No:
        if args:
            err("The command does not accept parameters. Discard {}.".format(args))
        if state & GitOptionState.Func:
            command()
        elif state & GitOptionState.String:
            echo("🌈  ", nl=False)
            echo(color_command(command))
            run_cmd(command)
        else:
            pass
    elif state & GitOptionState.Multi:
        if state & GitOptionState.Func:
            command(args)
        elif state & GitOptionState.String:
            if args:
                args_str = " ".join(args)
                command = " ".join([command, args_str])
            echo("🌈  ", nl=False)
            echo(color_command(command))
            run_cmd(command)
        else:
            pass
    else:
        pass


#####################################################################
# Print command help message.                                       #
#####################################################################
class HelpMsg(object):
    @staticmethod
    def echo_one_help_msg(k):
        """Print a tip.

        Find the corresponding help information according to the `k` value and
        print it. If the help information does not exist, print the executed
        full command.

        Args:
            k: Short command.
        """
        echo("    " + k, color=CommandColor.Green, nl=False)

        msg = GIT_OPTIONS[k]["help-msg"]
        command = GIT_OPTIONS[k]["command"]

        if callable(command):
            command = "Callable: %s" % command.__name__

        if len(command) > 100:
            command = command[:70] + " ..."

        if msg:
            echo((9 - len(k)) * " " + str(msg))
            echo(13 * " " + str(command), color=CommandColor.Gold)
        else:
            echo((9 - len(k)) * " " + str(command), color=CommandColor.Gold)

    @classmethod
    def echo_help_msgs(cls):
        """Print help message."""
        echo("These are short commands that can replace git operations:")
        for k in GIT_OPTIONS.keys():
            cls.echo_one_help_msg(k)

    @classmethod
    def echo_tip_with_type(cls, command_type):
        """Print a part of help message.

        Print the help information of the corresponding part according to the
        incoming command type string. If there is no print error prompt for the
        type.

        Args:
            command_type: A command type of `TYPE`.
        """
        command_type = (
            command_type[0].upper() + command_type[1:].lower()
            if len(command_type) > 1
            else command_type
        )
        if command_type not in TYPES:
            err("There is no such type.")
            echo("Please use `", nl=False)
            echo("g --types", color=CommandColor.Green, nl=False)
            echo(
                "` to view the supported types.",
            )
            predicted_type = similar_command(command_type, TYPES)
            echo(
                "🧐 The wanted type is %s ?"
                % (CommandColor.Green + predicted_type + Fx.reset),
                nl=False,
            )
            flag = confirm("[y/n]:")
            if flag:
                command_g(["-S", predicted_type])
            raise SystemExit(0)

        echo("These are the orders of {}".format(command_type))
        prefix = command_type[0].lower()
        for k in GIT_OPTIONS.keys():
            if k.startswith(prefix):
                cls.echo_one_help_msg(k)

    @staticmethod
    def echo_types():
        """Print all command types with random color."""
        for t in TYPES:
            echo(
                "{}{}  ".format(
                    Color.fg(
                        random.randint(0, 255),
                        random.randint(0, 255),
                        random.randint(0, 255),
                    ),
                    t,
                ),
                nl=False,
            )
        echo(Fx.reset)


#####################################################################
# Injection Completion Script.                                      #
#####################################################################
_TEMPLATE_ZSH = """\
#compdef g

complete_g(){
local curcontext="$curcontext" state line ret=1
typeset -A opt_args

_alternative\\
  \'args:options arg:((\\
    -c\:"Add shell prompt script and exit.(Supported `bash`, `zsh`)"\\
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
    --count\:"Count the number of codes and output them in tabular form."\\

    %s
  ))\'\\
  'files:filename:_files'
return ret
}

compdef complete_g g
"""

_TEMPLATE_BASH = """\
#!/usr/env bash

_complete_g(){
  if [[ "${COMP_CWORD}" == "1" ]];then
    COMP_WORD="-c --complete -s --show-commands -S --show-command -t --types\\
        -f --config -i --information -v --version --create-ignore\\
        --debug --out-log --count\\
         %s"
    COMPREPLY=($(compgen -W "$COMP_WORD" -- ${COMP_WORDS[${COMP_CWORD}]}))
  fi
}

complete -F _complete_g g
"""


class Completion(object):
    """Implement and inject help classes for completion scripts."""

    @staticmethod
    def get_current_shell():
        """Gets the currently used shell.

        Returns:
            shell_: Current shell string.
        """
        current_shell = ""
        _, resp = run_cmd_with_resp("echo $SHELL")
        if resp:
            current_shell = resp.split("/")[-1].strip()
        return current_shell

    @staticmethod
    def ensure_config_path(file_name):
        """Check config path.

        Check whether the configuration directory exists, if not, try to create
        it. Failed to exit, successfully returned to complete the file path.

        Args:
            file_name: Completion prompt script name.

        Returns:
            file_path: Full path of completion prompt script.
        """
        Log.debug("{}, {}".format(TOOLS_HOME, file_name))
        ensure_path(TOOLS_HOME)

        return "{}/{}".format(TOOLS_HOME, file_name)

    @staticmethod
    def generate_complete_script(template, fn, name="_g"):
        """Generate completion scirpt.

        Generate the completion script of the corresponding shell according to
        the template.

        Args:
            template: Script template.
            fn: Method of generating script content.
            name: Completion script name.
        """
        complete_src = fn()
        script_src = template % (complete_src)

        try:
            with open("%s/%s" % (TOOLS_HOME, name), "w") as f:
                for line in script_src:
                    f.write(line)
        except Exception as e:
            exit_(1, e)

    @staticmethod
    def using_completion(file_name, path, config_path):
        """Try using completion script.

        Inject the load of completion script into the configuration of shell.
        If it exists in the configuration, the injection will not be repeated.

        Args:
            file_name: generated completion script.
            path: `fungit` configuration path.
            config_path: shell configuration path.
        """
        try:
            with open(config_path) as f:
                shell_conf = f.read()
                _re = re.compile(r"\/\.config\/pygittools/([^\s]+)")
                files = _re.findall(shell_conf)
        except Exception as e:
            exit_(1, e)

        has_injected = False
        if files:
            for file in files:
                if file == file_name:
                    has_injected = True
        Log.debug("has_injected: {}".format(has_injected))

        if not has_injected:
            try:
                run_cmd('echo "source %s" >> %s ' % (path, config_path))
            except Exception as e:
                exit_(1, e)
            okay("\nPlease run: source {}".format(config_path))
        else:
            warn("This configuration already exists. 😅")

    @classmethod
    def add_zsh_completion(cls):
        """Add Zsh completion prompt script."""

        _name = "_g"
        _path = cls.ensure_config_path(_name)

        def gen_completion():
            vars = []

            for k in GIT_OPTIONS.keys():
                desc = GIT_OPTIONS[k]["help-msg"]
                if not desc:
                    desc = "no description."
                vars.append('    {}\\:"{}"\\'.format(k, desc))

            return ("\n".join(vars)).strip()

        cls.generate_complete_script(_TEMPLATE_ZSH, gen_completion, _name)

        cls.using_completion(_name, _path, USER_HOME + "/.zshrc")

    @classmethod
    def add_bash_completion(cls):
        """Add Bash completion prompt script."""

        _name = "complete_script"
        _path = cls.ensure_config_path(_name)

        def gen_completion():
            return " ".join(GIT_OPTIONS.keys())

        cls.generate_complete_script(_TEMPLATE_BASH, gen_completion, _name)

        cls.using_completion(_name, _path, USER_HOME + "/.bashrc")

    @classmethod
    def complete(cls):
        """Add completion prompt script."""
        echo("\nTry to add completion ...")

        current_shell = cls.get_current_shell()
        echo("Detected shell: %s" % current_shell)

        if current_shell == "zsh":
            cls.add_zsh_completion()
        elif current_shell == "bash":
            cls.add_bash_completion()
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
    err, res = run_cmd_with_resp("git branch --all --color")
    if err:
        branches = error_str
    else:
        branches = "\n".join(["\t" + x for x in res.strip().split("\n")])

    # Get the lastest log.
    err, res = run_cmd_with_resp("git log --stat --oneline --decorate -1 --color")
    if err:
        git_log = error_str
    else:
        git_log = "\n".join(["\t" + x for x in res.strip().split("\n")])

    echo(
        (
            "\r[%s]        \n"
            "Repository: \n\t%s\n"
            "Remote: \n%s\n"
            "Branches: \n%s\n"
            "Lastest log:\n%s"
            % (
                Fx.b + "Info" + Fx.reset,
                CommandColor.SkyBlue + Repository_Path + Fx.reset,
                remote,
                branches,
                git_log,
            )
        )
    )


class CodeCounter(object):
    rules = [
        {"pattern": re.compile(r"\.git"), "include": False},
        {
            # Exclude all picture formats.
            "pattern": re.compile(
                r"\.xbm|\.tif|\.pjp|\.svgz|\.jpg|\.jpeg|\.ico|\.icns|\.tiff|\.gif|\.svg|\.jfif|\.webp|\.png|\.bmp|\.jpeg|\.avif$",
                re.I,
            ),
            "include": False,
        },
        {
            # Exclude all video formats.
            "pattern": re.compile(
                r"\.avi|\.rmvb|\.rm|\.asf|\.divx|\.mpg|\.mpeg|\.mpe|\.wmv|\.mp4|\.mkv|\.vob",
                re.I,
            ),
            "include": False,
        },
        {
            # Exclude all audio frequency formats.
            "pattern": re.compile(
                r"\.mp3|\.wma|\.mid[i]?|\.mpeg|\.cda|\.wav|\.ape|\.flac|\.aiff|\.au",
                re.I,
            ),
            "include": False,
        },
        {
            # Exclude all font formats.
            "pattern": re.compile(
                r"\.otf|\.woff|\.woff2|\.ttf|\.eot",
                re.I,
            ),
            "include": False,
        },
    ]

    FileTypes = {
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
        if ".gitignore" in files:
            with open(os.path.join(root, ".gitignore")) as f:
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
                        item = os.path.join(root, "**", item)
                    else:
                        item = os.path.join(root, item)

                    item = re.sub(r"([\{\}\(\)\+\.\^\$\|])", r"\1", item)
                    item = re.sub(r"(^|[^\\])\?", ".", item)
                    item = re.sub(r"\/\*\*", "([\\\\/][^\\\\/]+)?", item)
                    item = re.sub(r"\*\*\/", "([^\\\\/]+[\\\\/])?", item)
                    item = re.sub(r"\*", "([^\\\\/]+)", item)
                    item = re.sub(r"\?", "*", item)
                    item = re.sub(r"([^\/])$", r"\1(([\\\\/].*)|$)", item)
                    item = re.sub(r"\/$", "(([\\\\/].*)|$)", item)
                    cls.rules.append(
                        {"pattern": re.compile(item), "include": is_negative}
                    )

    @classmethod
    def matching(cls, full_path):
        """Judge whether it is the required file according to the rule matching path.
        Returns `True` if the file not needs to be ignored, or `False` if needs.
        """
        res = list(filter(lambda rule: rule["pattern"].search(full_path), cls.rules))
        if not res or list(filter(lambda rule: rule["include"] == True, res)):
            return True
        else:
            return False

    # @staticmethod
    # def count_file_thread(full_path):
    #     pass

    @staticmethod
    def count_err_callback(e):
        """Handle of processing walk error."""
        print(e)
        raise SystemExit(0)

    @classmethod
    def count(cls, root_path=".", use_ignore=True):
        """Statistics file and returns the result dictionary.

        Return:
            result (dict): Dictionary containing statistical results.
            >>> result = {
            ...     'py': {
            ...         'files': 5,
            ...         'lines': 2124,
            ...     }
            ... }
        """

        result = {}
        valid_counter = 0
        invalid_counter = 0
        invalid_list = []
        for root, _, files in os.walk(
            root_path,
            onerror=cls.count_err_callback,
        ):

            if use_ignore:
                cls.process_gitignore(root, files)

            # First judge whether the directory is valid. Invalid directories
            # do not traverse files.
            is_effective_dir = cls.matching(root)
            if not is_effective_dir:
                continue

            for file in files:
                full_path = os.path.join(root, file)
                is_effective = cls.matching(full_path)
                if is_effective:
                    suffix = file.split(".")[-1]
                    suffix = cls.FileTypes.get(suffix.lower(), suffix)
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
                        echo(
                            "\rValid files found: {}, Invalid files found: {}".format(
                                valid_counter, invalid_counter
                            ),
                            nl=False,
                        )

        # from pprint import pprint

        # pprint(cls.rules)
        echo("")
        return result, invalid_list

    @staticmethod
    def recorded_result(root_path):
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
        """Save the record result to `TOOLS_HOME`/Counter"""

        file_name = root_path.replace("/", "_").replace("\\", "_").replace(".", "_")
        file_path = os.path.join(CodeCounter.Result_Saved_Path, file_name)
        ensure_path(CodeCounter.Result_Saved_Path)
        try:
            with open(file_path, "w") as wf:
                json.dump(result, wf, indent=2)
                return True
        except Exception:
            return False

    @staticmethod
    def format_print(d, old=None):
        """Try to load the record result from `TOOLS_HOME`/Counter"""

        echo(time.strftime("%H:%M:%S %a %Y-%m-%d %Z", time.localtime()))
        echo("{}{:^52}{}".format(Fx.bold, "[Code Counter Result]", Fx.unbold))
        echo("-" * 65)
        echo(
            "| {bold}{:<21}{unbold}| {bold}{:<17}{unbold}| {bold}{:<20}{unbold}|".format(
                "Language", "Files", "Code lines", bold=Fx.bold, unbold=Fx.unbold
            )
        )
        echo("-" * 65)
        sum = 0
        additions = 0
        deletions = 0
        for key, value in d.items():
            # Processing too long name.
            if len(key) > 20:
                key = "..." + key[-17:]

            # Set color.
            if value["lines"] <= 10000:
                lines_color = ""
            elif value["lines"] <= 100000:
                lines_color = CommandColor.Yellow
            else:
                lines_color = CommandColor.Red

            # Compare change.
            if isinstance(old, dict) and old.get(key, None) is not None:
                old_files = old.get(key).get("files", None)
                old_lines = old.get(key).get("lines", None)

                if value["files"] > old_files:
                    files_symbol = "+"
                    files_change = value["files"] - old_files
                elif value["files"] < old_files:
                    files_symbol = "-"
                    files_change = old_files - value["files"]
                else:
                    files_symbol = files_change = ""

                if value["lines"] > old_lines:
                    lines_symbol = "+"
                    lines_change = value["lines"] - old_lines
                    additions += lines_change
                elif value["lines"] < old_lines:
                    lines_symbol = "-"
                    lines_change = old_lines - value["lines"]
                    deletions += lines_change
                else:
                    lines_symbol = lines_change = ""

            else:
                files_change = files_symbol = lines_change = lines_symbol = ""

            # TODO: You can try adding color.
            print(
                "| {:<21}| {file_style}{:<11}{reset} {file_change_style}{file_change:>5}{reset}| {lines_style}{:<13}{reset} {line_change_style}{line_change:>6}{reset}|".format(
                    key,
                    value["files"],
                    value["lines"],
                    file_style=Fx.italic,
                    file_change_style=CommandColor.Symbol.get(files_symbol, ""),
                    file_change=files_symbol + str(files_change),
                    lines_style=lines_color,
                    line_change_style=CommandColor.Symbol.get(lines_symbol, ""),
                    line_change=lines_symbol + str(lines_change),
                    reset=Fx.reset,
                )
            )
            sum += value["lines"]
        echo("-" * 65)
        echo(" Total: {}".format(sum))
        if additions > 0 or deletions > 0:
            echo(" Altered: ", nl=False)
            echo("+" * ceil(additions / 10), color=CommandColor.Green, nl=False)
            echo("-" * ceil(deletions / 10), color=CommandColor.Red)

    @classmethod
    def count_and_format_print(
        cls, root_path=os.path.abspath(os.path.curdir), use_ignore=True, if_save=True
    ):
        result, invalid_list = cls.count(root_path, use_ignore)
        old_result = cls.recorded_result(root_path)
        cls.format_print(result, old_result)
        if if_save:
            cls.save_result(result, root_path)
        if invalid_list and confirm(
            "Wether print invalid file list?[y/n]", default=False
        ):
            print(invalid_list)


class GitignoreGenetor(object):

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
    def get_ignore_from_url(url):
        """Crawl gitignore template."""
        try:
            handle = urlopen(url, timeout=60)
        except Exception:
            err("Failed to get content and will exit.")
            raise SystemExit(0)

        content = handle.read().decode("utf-8")

        text = re.findall(r"(<table.*?>.*?<\/table>)", content, re.S)
        if not text:
            return ""

        content_re = re.compile(r"<\/?\w+.*?>", re.S)
        res = content_re.sub("", text[0])
        res = re.sub(r"(\n[^\S\r\n]+)+", "\n", res)
        return res

    @classmethod
    def create_gitignore(cls, genre):
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
            ignore_content = cls.get_ignore_from_url(target_url)

            echo("Got content, trying to write ... ")
            try:
                with open(ignore_path, "w") as f:
                    f.write(ignore_content)
                echo("Write gitignore file successful.😊")
            except Exception:
                err("Write gitignore file failed.")


def version():
    """Print version info."""
    echo("Version: %s" % __version__)


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
            % (CommandColor.SkyBlue + Fx.underline + __git_url__)
        ),
        style=Fx.italic,
    )

    echo("\nYou can use ", nl=False)
    echo("-h", color=CommandColor.Green, nl=False)
    echo(" and ", nl=False)
    echo("--help", color=CommandColor.Green, nl=False)
    echo(" to get help and more usage.\n")


@time_testing
def command_g(custom_commands=None):
    try:
        signal.signal(signal.SIGINT, exit_)
    except Exception:
        pass

    args = argparse.ArgumentParser(
        prog="g",
        description="If you want to use some original git commands, please use -- to indicate.",
    )
    args.add_argument(
        "-c",
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
        % ", ".join(TYPES),
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
        "-v", "--version", action="store_true", help="Show version and exit."
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
        "--count",
        action="store_true",
        help="Count the number of codes and output them in tabular form.",
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
        Completion.complete()
        raise SystemExit(0)

    if stdargs.show_commands:
        HelpMsg.echo_help_msgs()
        raise SystemExit(0)

    if stdargs.command_type:
        HelpMsg.echo_tip_with_type(stdargs.command_type)
        raise SystemExit(0)

    if stdargs.types:
        HelpMsg.echo_types()
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

    if stdargs.count:
        CodeCounter.count_and_format_print()
        raise SystemExit(0)

    if stdargs.version:
        version()
        raise SystemExit(0)

    if stdargs.command:
        if stdargs.command == "|":
            introduce()
        else:
            command = stdargs.command
            process_command(command, stdargs.args)


if __name__ == "__main__":
    command_g()
