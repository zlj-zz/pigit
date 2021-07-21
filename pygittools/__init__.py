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
__version__ = "1.0.0"
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


USER_HOME = os.environ["HOME"]
TOOLS_HOME = USER_HOME + "/.config/pygittools"
Log = logging.getLogger(__name__)


###################################### Utils
def ensure_path(file_path):
    """Determine whether the file path exists. If not, create a directory.
    Args:
        file_path: (str), like: "~/.config/xxx/xxx.log"
    """
    if not os.path.exists(file_path):
        dir_path = os.path.dirname(file_path)
        os.makedirs(dir_path, exist_ok=True)


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
    try:
        with subprocess.Popen(" ".join(args), shell=True) as proc:
            proc.wait()
    except Exception as e:
        Log.warning(e)


def run_cmd_with_resp(*args):
    try:
        with subprocess.Popen(
            " ".join(args), stderr=subprocess.PIPE, stdout=subprocess.PIPE, shell=True
        ) as proc:
            res = proc.stdout.read().decode()
            err = proc.stderr.read().decode()
            return err, res
    except Exception as e:
        Log.warning(e)
        print(e)
        return e, ""


def git_version():
    """Get Git version."""
    try:
        _, git_version = run_cmd_with_resp("git --version")
        if git_version:
            return git_version
        else:
            return None
    except Exception:
        Log.warning("Can not found Git in environment.")
        return None


#################################### Log
FMT_NORMAL = logging.Formatter(
    fmt="%(asctime)s %(levelname).4s %(message)s", datefmt="%H:%M:%S"
)
FMT_DEBUG = logging.Formatter(
    fmt="%(asctime)s.%(msecs)03d %(levelname).4s [%(name)s] %(message)s",
    datefmt="%H:%M:%S",
)


def setup_logging(debug=False, log_file="-"):
    root_logger = logging.getLogger()

    if debug:
        log_level = logging.DEBUG
        formatter = FMT_DEBUG
    else:
        log_level = logging.INFO
        formatter = FMT_NORMAL

    if log_file:
        if log_file == "-":
            log_handle = logging.StreamHandler()
        else:
            ensure_path(log_file)
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


# def current_repository():
#     err, path = run_cmd_with_resp("git rev-parse --git-dir")

#     if err:
#         return ""

#     path = path.strip()
#     if path == ".git":
#         repository_path = os.getcwd()
#     else:
#         repository_path = "/".join(path.split("/")[:-1])
#     return repository_path


################################## Style


class Color(object):
    """Holds representations for a 24-bit color value
    __init__(color, depth="fg", default=False)
    -- color accepts 6 digit hexadecimal: string "#RRGGBB", 2 digit hexadecimal: string "#FF" or decimal RGB "255 255 255" as a string.
    -- depth accepts "fg" or "bg"
    __call__(*args) joins str arguments to a string and apply color
    __str__ returns escape sequence to set color
    __iter__ returns iteration over red, green and blue in integer values of 0-255.
    * Values:  .hexa: str  |  .dec: Tuple[int, int, int]  |  .red: int  |  .green: int  |  .blue: int  |  .depth: str  |  .escape: str
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


class Fx(object):
    """Text effects
    * trans(string: str): Replace whitespace with escape move right to not overwrite background behind whitespace.
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


class CommandColor:
    """Terminal print color class."""

    RED = Color.fg("#FF6347")  # Tomato
    GREEN = Color.fg("#98FB98")  # PaleGreen
    YELLOW = Color.fg("#FFD700")  # Gold


############################## Output
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


def okay(msg):
    """Print green information."""
    echo("%s%s%s%s" % (Fx.b, CommandColor.GREEN, msg, Fx.reset))


def warn(msg):
    """Print yellow information."""
    echo("%s%s%s%s" % (Fx.b, CommandColor.YELLOW, msg, Fx.reset))


def err(msg):
    """Print red information."""
    echo("%s%s%s%s" % (Fx.b, CommandColor.RED, msg, Fx.reset))


########################## Command
class GitOptionState:
    NO = 0
    ONE = 1
    MULTI = 1 << 1
    INTERC = 1 << 2
    FUNC = 1 << 3
    STRING = 1 << 4


def add(args):
    if args:
        args_str = " ".join(args)
    else:
        args_str = " ."

    run_cmd("git add " + args_str)


def fetch_remote_branch(args):
    branch = args[0] if len(args) > 1 else None

    if branch:
        run_cmd("git fetch origin {}:{} ".format(branch, branch))
    else:
        warn("This option need a branch name.")


def set_email_and_username(args):
    __global = re.compile(r"\-\-global")
    res = []
    for i in args:
        r = __global.search(i)
        if r is not None:
            res.append(i)
    if res:
        other = " --global "
    else:
        other = " "

    name = input("Please input username:")
    run_cmd(GIT_OPTIONS["user"]["command"] + other + name)
    email = input("Please input email:")
    run_cmd(GIT_OPTIONS["email"]["command"] + other + email)


def process_func(c, args):
    fn = GIT_OPTIONS[c]["command"]
    fn(args)


def process_origin_command(c, args):
    origin_command = GIT_OPTIONS[c]["command"]

    if args:
        args_str = " ".join(args)
        command = " ".join([origin_command, args_str])
    else:
        command = origin_command

    warn(command)
    run_cmd(command)


def process(c, args=None):
    try:
        state = GIT_OPTIONS[c]["state"]
    except Exception:
        echo("Don't support this command, please try ", nl=False)
        warn("g --show-commands")
        raise SystemExit(0)

    if state & GitOptionState.FUNC:
        process_func(c, args)
    elif state & GitOptionState.STRING:
        process_origin_command(c, args)


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
        "state": GitOptionState.STRING | GitOptionState.NO,
        "command": "git branch ",
        "help-msg": "lists, creates, renames, and deletes branches.",
    },
    "bc": {
        "state": GitOptionState.STRING | GitOptionState.ONE,
        "command": "git checkout -b ",
        "help-msg": "creates a new branch.",
    },
    "bl": {
        "state": GitOptionState.STRING | GitOptionState.NO,
        "command": "git branch -vv ",
        "help-msg": "lists branches and their commits.",
    },
    "bL": {
        "state": GitOptionState.STRING | GitOptionState.NO,
        "command": "git branch --all -vv ",
        "help-msg": "lists local and remote branches and their commits.",
    },
    "bs": {
        "state": GitOptionState.STRING | GitOptionState.NO,
        "command": "git show-branch ",
        "help-msg": "lists branches and their commits with ancestry graphs.",
    },
    "bS": {
        "state": GitOptionState.STRING | GitOptionState.NO,
        "command": "git show-branch --all ",
        "help-msg": "lists local and remote branches and their commits with ancestry graphs.",
    },
    "bm": {
        "state": GitOptionState.STRING | GitOptionState.ONE,
        "command": "git branch --move ",
        "help-msg": "renames a branch.",
    },
    "bM": {
        "state": GitOptionState.STRING | GitOptionState.ONE,
        "command": "git branch --move --force ",
        "help-msg": "renames a branch even if the new branch name already exists.",
    },
    # Commit
    "c": {
        "state": GitOptionState.STRING | GitOptionState.MULTI,
        "command": "git commit --verbose ",
        "help-msg": "records changes to the repository.",
    },
    "ca": {
        "state": GitOptionState.STRING | GitOptionState.MULTI,
        "command": "git commit --verbose --all ",
        "help-msg": "commits all modified and deleted files.",
    },
    "cA": {
        "state": GitOptionState.STRING | GitOptionState.MULTI,
        "command": "git commit --verbose --patch ",
        "help-msg": "commits all modified and deleted files interactivly.",
    },
    "cm": {
        "state": GitOptionState.STRING | GitOptionState.ONE,
        "command": "git commit --verbose --message ",
        "help-msg": "commits with the given message.",
    },
    "co": {
        "state": GitOptionState.STRING | GitOptionState.MULTI,
        "command": "git checkout ",
        "help-msg": "checks out a branch or paths to the working tree.",
    },
    "cO": {
        "state": GitOptionState.STRING | GitOptionState.MULTI,
        "command": "git checkout --pathc ",
        "help-msg": "checks out hunks from the index or the tree interactively.",
    },
    "cf": {
        "state": GitOptionState.STRING | GitOptionState.NO,
        "command": "git commit --amend --reuse-message HEAD ",
        "help-msg": "amends the tip of the current branch reusing the same log message as HEAD.",
    },
    "cF": {
        "state": GitOptionState.STRING | GitOptionState.MULTI,
        "command": "git commit --verbose --amend ",
        "help-msg": "amends the tip of the current branch.",
    },
    "cr": {
        "state": GitOptionState.STRING | GitOptionState.MULTI,
        "command": "git revert ",
        "help-msg": "reverts existing commits by reverting patches and recording new commits.",
    },
    "cR": {
        "state": GitOptionState.STRING | GitOptionState.NO,
        "command": 'git reset "HEAD^" ',
        "help-msg": "removes the HEAD commit.",
    },
    "cs": {
        "state": GitOptionState.STRING | GitOptionState.MULTI,
        "command": 'git show --pretty=format:"%C(bold yellow)commit %H%C(auto)%d%n%C(bold)Author: %C(blue)%an <%ae> %C(reset)%C(cyan)%ai (%ar)%n%C(bold)Commit: %C(blue)%cn <%ce> %C(reset)%C(cyan)%ci (%cr)%C(reset)%n%+B"',
        "help-msg": "shows one or more objects (blobs, trees, tags and commits).",
    },
    # Conflict(C)
    "Cl": {
        "state": GitOptionState.STRING | GitOptionState.NO,
        "command": "git --no-pager diff --diff-filter=U --name-only ",
        "help-msg": "lists unmerged files.",
    },
    "Ca": {
        "state": GitOptionState.STRING | GitOptionState.MULTI,
        "command": "git add git --no-pager diff --diff-filter=U --name-only ",
        "help-msg": "adds unmerged file contents to the index.",
    },
    "Ce": {
        "state": GitOptionState.STRING | GitOptionState.MULTI,
        "command": "git mergetool git --no-pager diff --diff-filter=U --name-only ",
        "help-msg": "executes merge-tool on all unmerged files.",
    },
    "Co": {
        "state": GitOptionState.STRING | GitOptionState.MULTI,
        "command": "git checkout --ours -- ",
        "help-msg": "checks out our changes for unmerged paths.",
    },
    "CO": {
        "state": GitOptionState.STRING | GitOptionState.NO,
        "command": "git checkout --ours -- git --no-pager diff --diff-filter=U --name-only ",
        "help-msg": "checks out our changes for all unmerged paths.",
    },
    "Ct": {
        "state": GitOptionState.STRING | GitOptionState.MULTI,
        "command": "git checkout --theirs -- ",
        "help-msg": "checks out their changes for unmerged paths.",
    },
    "CT": {
        "state": GitOptionState.STRING | GitOptionState.NO,
        "command": "git checkout --theirs -- git --no-pager diff --diff-filter=U --name-only ",
        "help-msg": "checks out their changes for all unmerged paths.",
    },
    # Fetch(f)
    "f": {
        "state": GitOptionState.STRING | GitOptionState.MULTI,
        "command": "git fetch ",
        "help-msg": "downloads objects and references from another repository.",
    },
    "fc": {
        "state": GitOptionState.STRING | GitOptionState.MULTI,
        "command": "git clone ",
        "help-msg": "clones a repository into a new directory.",
    },
    "fC": {
        "state": GitOptionState.STRING | GitOptionState.MULTI,
        "command": "git clone --depth=1 ",
        "help-msg": "clones a repository into a new directory clearly(depth:1).",
    },
    "fm": {
        "state": GitOptionState.STRING | GitOptionState.MULTI,
        "command": "git pull ",
        "help-msg": "fetches from and merges with another repository or local branch.",
    },
    "fr": {
        "state": GitOptionState.STRING | GitOptionState.MULTI,
        "command": "git pull --rebase ",
        "help-msg": "fetches from and rebase on top of another repository or local branch.",
    },
    "fu": {
        "state": GitOptionState.STRING | GitOptionState.MULTI,
        "command": "git fetch --all --prune && git merge --ff-only @{u} ",
        "help-msg": "removes un-existing remote-tracking references, fetches all remotes and merges.",
    },
    "fb": {
        "state": GitOptionState.FUNC | GitOptionState.ONE,
        "command": fetch_remote_branch,
        "help-msg": "fetch other branch to local as same name.",
    },
    # Index(i)
    "ia": {
        "state": GitOptionState.FUNC | GitOptionState.MULTI,
        "command": add,
        "help-msg": "adds file contents to the index(default: all files).",
    },
    "iA": {
        "state": GitOptionState.STRING | GitOptionState.MULTI,
        "command": "git add --patch ",
        "help-msg": "adds file contents to the index interactively.",
    },
    "iu": {
        "state": GitOptionState.STRING | GitOptionState.MULTI,
        "command": "git add --update ",
        "help-msg": "adds file contents to the index (updates only known files).",
    },
    "id": {
        "state": GitOptionState.STRING | GitOptionState.MULTI,
        "command": "git diff --no-ext-diff --cached ",
        "help-msg": "displays changes between the index and a named commit (diff).",
    },
    "iD": {
        "state": GitOptionState.STRING | GitOptionState.MULTI,
        "command": "git diff --no-ext-diff --cached --word-diff ",
        "help-msg": "displays changes between the index and a named commit (word diff).",
    },
    "ir": {
        "state": GitOptionState.STRING | GitOptionState.MULTI,
        "command": "git reset ",
        "help-msg": "resets the current HEAD to the specified state.",
    },
    "iR": {
        "state": GitOptionState.STRING | GitOptionState.MULTI,
        "command": "git reset --patch ",
        "help-msg": "resets the current index interactively.",
    },
    "ix": {
        "state": GitOptionState.STRING | GitOptionState.MULTI,
        "command": "git rm --cached -r ",
        "help-msg": "removes files from the index (recursively).",
    },
    "iX": {
        "state": GitOptionState.STRING | GitOptionState.MULTI,
        "command": "git rm --cached -rf ",
        "help-msg": "removes files from the index (recursively and forced).",
    },
    # Log(l)
    "l": {
        "state": GitOptionState.STRING | GitOptionState.MULTI,
        "command": "git log --graph --all --decorate ",
        "help-msg": "displays the log with good format.",
    },
    "l1": {
        "state": GitOptionState.STRING | GitOptionState.MULTI,
        "command": "git log --graph --all --decorate --oneline ",
        "help-msg": "",
    },
    "ls": {
        "state": GitOptionState.STRING | GitOptionState.NO,
        "command": 'git log --topo-order --stat --pretty=format:"%C(bold yellow)commit %H%C(auto)%d%n%C(bold)Author: %C(blue)%an <%ae> %C(reset)%C(cyan)%ai (%ar)%n%C(bold)Commit: %C(blue)%cn <%ce> %C(reset)%C(cyan)%ci (%cr)%C(reset)%n%+B" ',
        "help-msg": "displays the stats log.",
    },
    "ld": {
        "state": GitOptionState.STRING | GitOptionState.NO,
        "command": 'git log --topo-order --stat --patch --pretty=format:"%C(bold yellow)commit %H%C(auto)%d%n%C(bold)Author: %C(blue)%an <%ae> %C(reset)%C(cyan)%ai (%ar)%n%C(bold)Commit: %C(blue)%cn <%ce> %C(reset)%C(cyan)%ci (%cr)%C(reset)%n%+B" ',
        "help-msg": "displays the diff log.",
    },
    "lv": {
        "state": GitOptionState.STRING | GitOptionState.NO,
        "command": 'git log --topo-order --show-signature --pretty=format:"%C(bold yellow)commit %H%C(auto)%d%n%C(bold)Author: %C(blue)%an <%ae> %C(reset)%C(cyan)%ai (%ar)%n%C(bold)Commit: %C(blue)%cn <%ce> %C(reset)%C(cyan)%ci (%cr)%C(reset)%n%+B" ',
        "help-msg": "displays the log, verifying the GPG signature of commits.",
    },
    "lc": {
        "state": GitOptionState.STRING | GitOptionState.MULTI,
        "command": "git shortlog --summary --numbered ",
        "help-msg": "displays the commit count for each contributor in descending order.",
    },
    "lr": {
        "state": GitOptionState.STRING | GitOptionState.MULTI,
        "command": "git reflog ",
        "help-msg": "manages reflog information.",
    },
    # Merge(m)
    "m": {
        "state": GitOptionState.STRING | GitOptionState.MULTI,
        "command": "git merge ",
        "help-msg": "joins two or more development histories together.",
    },
    "ma": {
        "state": GitOptionState.STRING | GitOptionState.MULTI,
        "command": "git merge --abort ",
        "help-msg": "aborts the conflict resolution, and reconstructs the pre-merge state.",
    },
    "mC": {
        "state": GitOptionState.STRING | GitOptionState.MULTI,
        "command": "git merge --no-commit ",
        "help-msg": "performs the merge but does not commit.",
    },
    "mF": {
        "state": GitOptionState.STRING | GitOptionState.MULTI,
        "command": "git merge --no-ff ",
        "help-msg": "creates a merge commit even if the merge could be resolved as a fast-forward.",
    },
    "mS": {
        "state": GitOptionState.STRING | GitOptionState.MULTI,
        "command": "git merge -S ",
        "help-msg": "performs the merge and GPG-signs the resulting commit.",
    },
    "mv": {
        "state": GitOptionState.STRING | GitOptionState.MULTI,
        "command": "git merge --verify-signatures ",
        "help-msg": "verifies the GPG signature of the tip commit of the side branch being merged.",
    },
    "mt": {
        "state": GitOptionState.STRING | GitOptionState.MULTI,
        "command": "git mergetool ",
        "help-msg": "runs the merge conflict resolution tools to resolve conflicts.",
    },
    # Push(p)
    "p": {
        "state": GitOptionState.STRING | GitOptionState.MULTI,
        "command": "git push ",
        "help-msg": "updates remote refs along with associated objects.",
    },
    "pf": {
        "state": GitOptionState.STRING | GitOptionState.MULTI,
        "command": "git push --force-with-lease ",
        "help-msg": 'forces a push safely (with "lease").',
    },
    "pF": {
        "state": GitOptionState.STRING | GitOptionState.MULTI,
        "command": "git push --force ",
        "help-msg": "forces a push. ",
    },
    "pa": {
        "state": GitOptionState.STRING | GitOptionState.MULTI,
        "command": "git push --all ",
        "help-msg": "pushes all branches.",
    },
    "pA": {
        "state": GitOptionState.STRING | GitOptionState.MULTI,
        "command": "git push --all && git push --tags ",
        "help-msg": "pushes all branches and tags.",
    },
    "pt": {
        "state": GitOptionState.STRING | GitOptionState.MULTI,
        "command": "git push --tags ",
        "help-msg": "pushes all tags.",
    },
    "pc": {
        "state": GitOptionState.STRING | GitOptionState.MULTI,
        "command": 'git push --set-upstream origin "$(git symbolic-ref -q --short HEAD 2> /dev/null)" ',
        "help-msg": "pushes the current branch and adds origin as an upstream reference for it.",
    },
    "pp": {
        "state": GitOptionState.STRING | GitOptionState.MULTI,
        "command": 'git pull origin "$(git symbolic-ref -q --short HEAD 2> /dev/null)" && git push origin "$(git symbolic-ref -q --short HEAD 2> /dev/null)" ',
        "help-msg": "pulls and pushes the current branch from origin to origin.",
    },
    # Remote(R)
    "R": {
        "state": GitOptionState.STRING | GitOptionState.MULTI,
        "command": "git remote ",
        "help-msg": "manages tracked repositories.",
    },
    "Rl": {
        "state": GitOptionState.STRING | GitOptionState.MULTI,
        "command": "git remote --verbose ",
        "help-msg": "lists remote names and their URLs.",
    },
    "Ra": {
        "state": GitOptionState.STRING | GitOptionState.MULTI,
        "command": "git remote add ",
        "help-msg": "adds a new remote.",
    },
    "Rx": {
        "state": GitOptionState.STRING | GitOptionState.MULTI,
        "command": "git remote rm ",
        "help-msg": "removes a remote.",
    },
    "Rm": {
        "state": GitOptionState.STRING | GitOptionState.MULTI,
        "command": "git remote rename ",
        "help-msg": "renames a remote.",
    },
    "Ru": {
        "state": GitOptionState.STRING | GitOptionState.MULTI,
        "command": "git remote update ",
        "help-msg": "fetches remotes updates.",
    },
    "Rp": {
        "state": GitOptionState.STRING | GitOptionState.MULTI,
        "command": "git remote prune ",
        "help-msg": "prunes all stale remote tracking branches.",
    },
    "Rs": {
        "state": GitOptionState.STRING | GitOptionState.MULTI,
        "command": "git remote show ",
        "help-msg": "shows information about a given remote.",
    },
    "RS": {
        "state": GitOptionState.STRING | GitOptionState.MULTI,
        "command": "git remote set-url ",
        "help-msg": "changes URLs for a remote.",
    },
    # Stash(s)
    "s": {
        "state": GitOptionState.STRING | GitOptionState.MULTI,
        "command": "git stash ",
        "help-msg": "stashes the changes of the dirty working directory.",
    },
    "sp": {
        "state": GitOptionState.STRING | GitOptionState.MULTI,
        "command": "git stash pop ",
        "help-msg": "removes and applies a single stashed state from the stash list.",
    },
    "sl": {
        "state": GitOptionState.STRING | GitOptionState.MULTI,
        "command": "git stash list ",
        "help-msg": "lists stashed states.",
    },
    "sd": {
        "state": GitOptionState.STRING | GitOptionState.MULTI,
        "command": "git stash show",
        "help-msg": "",
    },
    "sD": {
        "state": GitOptionState.STRING | GitOptionState.MULTI,
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
        "state": GitOptionState.STRING | GitOptionState.MULTI,
        "command": "git tag ",
        "help-msg": "creates, lists, deletes or verifies a tag object signed with GPG.",
    },
    "ta": {
        "state": GitOptionState.STRING | GitOptionState.MULTI,
        "command": "git tag -a ",
        "help-msg": "create a new tag.",
    },
    "tx": {
        "state": GitOptionState.STRING | GitOptionState.MULTI,
        "command": "git tag --delete ",
        "help-msg": "deletes tags with given names.",
    },
    # Working tree(w)
    "ws": {
        "state": GitOptionState.STRING | GitOptionState.MULTI,
        "command": "git status --short ",
        "help-msg": "displays working-tree status in the short format.",
    },
    "wS": {
        "state": GitOptionState.STRING | GitOptionState.MULTI,
        "command": "git status ",
        "help-msg": "displays working-tree status.",
    },
    "wd": {
        "state": GitOptionState.STRING | GitOptionState.MULTI,
        "command": "git diff --no-ext-diff ",
        "help-msg": "displays changes between the working tree and the index (diff).",
    },
    "wD": {
        "state": GitOptionState.STRING | GitOptionState.MULTI,
        "command": "git diff --no-ext-diff --word-diff ",
        "help-msg": "displays changes between the working tree and the index (word diff).",
    },
    "wr": {
        "state": GitOptionState.STRING | GitOptionState.MULTI,
        "command": "git reset --soft ",
        "help-msg": "resets the current HEAD to the specified state, does not touch the index nor the working tree.",
    },
    "wR": {
        "state": GitOptionState.STRING | GitOptionState.MULTI,
        "command": "git reset --hard ",
        "help-msg": "resets the current HEAD, index and working tree to the specified state.",
    },
    "wc": {
        "state": GitOptionState.STRING | GitOptionState.MULTI,
        "command": "git clean --dry-run ",
        "help-msg": "cleans untracked files from the working tree (dry-run).",
    },
    "wC": {
        "state": GitOptionState.STRING | GitOptionState.MULTI,
        "command": "git clean -d --force ",
        "help-msg": "cleans untracked files from the working tree.",
    },
    "wm": {
        "state": GitOptionState.STRING | GitOptionState.MULTI,
        "command": "git mv ",
        "help-msg": "moves or renames files.",
    },
    "wM": {
        "state": GitOptionState.STRING | GitOptionState.MULTI,
        "command": "git mv -f ",
        "help-msg": "moves or renames files (forced).",
    },
    "wx": {
        "state": GitOptionState.STRING | GitOptionState.MULTI,
        "command": "git rm -r ",
        "help-msg": "removes files from the working tree and from the index (recursively).",
    },
    "wX": {
        "state": GitOptionState.STRING | GitOptionState.MULTI,
        "command": "git rm -rf ",
        "help-msg": "removes files from the working tree and from the index (recursively and forced).",
    },
    # Setting
    "savepd": {
        "state": GitOptionState.STRING | GitOptionState.MULTI,
        "command": "git config credential.helper store ",
        "help-msg": "Remember your account and password.",
    },
    "ue": {
        "state": GitOptionState.FUNC | GitOptionState.NO,
        "command": set_email_and_username,
        "help-msg": "set email and username interactively.",
    },
    "user": {
        "state": GitOptionState.STRING | GitOptionState.MULTI,
        "command": "git config user.name ",
        "help-msg": "",
    },
    "email": {
        "state": GitOptionState.STRING | GitOptionState.MULTI,
        "command": "git config user.email ",
        "help-msg": "",
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

########################### Completion
_TEMPLATE_ZSH = """\
#compdef g

complete_g(){
local curcontext="$curcontext" state line ret=1
typeset -A opt_args

_alternative\\
  \'args:options arg:((\\
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
    COMP_WORD="%s"
    COMPREPLY=($(compgen -W "$COMP_WORD" -- ${COMP_WORDS[${COMP_CWORD}]}))
  fi
}

complete -F _complete_g g
"""


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
    if not os.path.exists(TOOLS_HOME):
        try:
            os.mkdir(TOOLS_HOME)
        except Exception as e:
            exit_(1, e)

    file_path = "{}/{}".format(TOOLS_HOME, file_name)
    return file_path


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
        warn("This configuration already exists.")


def add_zsh_completion():
    """Add Zsh completion prompt script."""

    _name = "_g"
    _path = ensure_config_path(_name)

    def gen_completion():
        vars = []

        for k in GIT_OPTIONS.keys():
            desc = GIT_OPTIONS[k]["help-msg"]
            if not desc:
                desc = "no description."
            vars.append('    {}\\:"{}"\\\n'.format(k, desc))

        return ("\n".join(vars)).rstrip()

    generate_complete_script(_TEMPLATE_ZSH, gen_completion, _name)

    using_completion(_name, _path, USER_HOME + "/.zshrc")


def add_bash_completion():
    """Add Bash completion prompt script."""

    _name = "complete_script"
    _path = ensure_config_path(_name)

    def gen_completion():
        return " ".join(GIT_OPTIONS.keys())

    generate_complete_script(_TEMPLATE_BASH, gen_completion, _name)

    using_completion(_name, _path, USER_HOME + "/.bashrc")


def add_completion():
    """Add completion prompt script."""
    echo("\nTry to add completion ...")

    current_shell = get_current_shell()
    echo("Detect shell: %s" % current_shell)
    if current_shell == "zsh":
        add_zsh_completion()
    elif current_shell == "bash":
        add_bash_completion()
    else:
        warn("Don't support completion of %s" % current_shell)


#################### Help msg
def echo_one_help_msg(k):
    """Print a tip.

    Find the corresponding help information according to the `k` value and
    print it. If the help information does not exist, print the executed
    full command.

    Args:
        k: Short command.
    """
    echo("    " + k, color=CommandColor.GREEN, nl=False)

    msg = GIT_OPTIONS[k]["help-msg"]
    command = GIT_OPTIONS[k]["command"]

    if msg:
        echo((9 - len(k)) * " " + str(msg))
        echo(13 * " " + str(command), color=CommandColor.YELLOW)
    else:
        echo((9 - len(k)) * " " + str(command), color=CommandColor.YELLOW)


def echo_help_msgs():
    """Print help message."""
    echo("These are short commands that can replace git operations:")
    for k in GIT_OPTIONS.keys():
        echo_one_help_msg(k)


def give_tip(command_type):
    """Print a part of help message.

    Print the help information of the corresponding part according to the
    incoming command type string. If there is no print error prompt for the
    type.

    Args:
        command_type: A command type of `TYPE`.
    """
    command_type = (
        command_type[0].upper() + command_type[1:].lower()
        if len(command_type) > 2
        else ""
    )
    if command_type not in TYPES:
        err("There is no such type.")
        raise SystemExit(0)

    echo("These are the orders of {}".format(command_type))
    prefix = command_type[0].lower()
    for k in GIT_OPTIONS.keys():
        if k.startswith(prefix):
            echo_one_help_msg(k)


def echo_types():
    """Print all command types."""
    for t in TYPES:
        # TODO: may need new format.
        print(" {}".format(t))


def introduce():
    """Print the description information."""

    # Print tools version and path.
    echo("[%s] version: %s" % (__project__, __version__), style=Fx.b)
    echo("path: %s" % __name__)

    # Print git version.
    _git_version = git_version()
    if _git_version is None:
        warn("Don't found Git, maybe need install.")
    else:
        echo(_git_version)

    echo("Description:", style=Fx.b)
    echo(
        (
            "  Fungit terminal tool, help you use git more simple."
            " Support Linux and MacOS.\n"
        ),
        style=Fx.italic,
    )

    echo("You can use ", nl=False)
    echo("-h", color=CommandColor.GREEN, nl=False)
    echo(" and ", nl=False)
    echo("--help", color=CommandColor.GREEN, nl=False)
    echo(" to get how to use command fungit.\n")


def version():
    """Print version info."""
    echo("version: %s" % __version__)


def command_g(custom_commands=None):
    setup_logging(debug=False, log_file=TOOLS_HOME + "/log/gittools.log")

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
        help="Add shell prompt script and exit.",
    )
    args.add_argument(
        "-s",
        "--show-commands",
        action="store_true",
        help="List all available fame and wealth and exit.",
    )
    args.add_argument(
        "-S",
        "--show-command",
        type=str,
        metavar="TYPE",
        dest="command_type",
        help="According to given type list available fame and wealth and exit.",
    )
    args.add_argument(
        "-t",
        "--types",
        action="store_true",
        help="List all command type and exit.",
    )
    args.add_argument(
        "-v", "--version", action="store_true", help="Show version and exit."
    )
    args.add_argument(
        "command", nargs="?", default="|", type=str, help="Short git command."
    )
    args.add_argument("args", nargs="*", type=str, help="Command parameter list.")
    stdargs = args.parse_args()

    if custom_commands is not None:
        stdargs = args.parse_args(custom_commands)
    # print(stdargs)

    if stdargs.complete:
        add_completion()
        raise SystemExit(0)

    if stdargs.show_commands:
        echo_help_msgs()
        raise SystemExit(0)

    if stdargs.command_type:
        give_tip(stdargs.command_type)
        raise SystemExit(0)

    if stdargs.types:
        echo_types()
        raise SystemExit(0)

    if stdargs.version:
        version()
        raise SystemExit(0)

    if stdargs.command:
        if stdargs.command == "|":
            introduce()
        else:
            command = stdargs.command
            process(command, stdargs.args)


if __name__ == "__main__":
    command_g()
