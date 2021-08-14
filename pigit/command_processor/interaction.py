# -*- coding:utf-8 -*-

from __future__ import division, print_function
import os
import sys
import signal
import time
from math import ceil

# try to import needed pkg.
# If import failed, set `TERM_CONTROL` is False.
try:
    import select, termios, fcntl, tty  # noqa: E401

    TERM_CONTROL = True
except Exception:
    TERM_CONTROL = False

from ..compat import get_terminal_size, B
from ..utils import exec_cmd, run_cmd, confirm
from ..str_utils import shorten, get_width
from ..common import Fx, Color, TermColor
from .model import File


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
# Part of command.                                                  #
#####################################################################
class TermError(Exception):
    pass


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
                        TermColor.Green,
                        staged_change,
                        TermColor.Red,
                        unstaged_change,
                        display_name,
                        Fx.reset,
                    )
                else:
                    display_str = "{}{} {}{}".format(
                        TermColor.Red, change, display_name, Fx.reset
                    )
            else:
                display_str = "{}{} {}{}".format(
                    TermColor.Green, change, display_name, Fx.reset
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
            print(Fx.clear_)
            print(str([i[1] for i in diff_]))
            input()

        extra = 0  # Extra occupied row.
        while not stopping:
            print(Fx.clear_)

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
                print(Fx.clear_)
                print(
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
        print(Fx.clear_)
        if confirm("discard all changed? [y/n]:"):
            if file.tracked:
                run_cmd("git checkout -- {}".format(file.name))
            else:
                os.remove(os.path.join(file.name))

    def add_interactive(self, *args):
        """Interactive main method."""

        # Wether can into interactive.
        if not TERM_CONTROL:
            raise TermError("This behavior is not supported in the current system.")

        width, height = get_terminal_size()
        if height < self._min_height or width < self._min_width:
            raise TermError("The minimum size of terminal should be 60 x 5.")

        if self._debug:  # debug show.
            print(Fx.clear_)
            print(width, height)
            time.sleep(1.5)

        # Initialize.
        cursor_row = 1
        cursor_icon = self.cursor
        display_range = [1, height - 1]

        stopping = False

        # Into new term page.
        print(Fx.alt_screen + Fx.hide_cursor)

        file_items = self.get_status(width)
        try:
            KeyEvent.signal_init()

            # Start interactive.
            while not stopping:
                print(Fx.clear_)
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
                            '{} "{}"'.format(editor, file_items[cursor_row - 1].name)
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
                    print(Fx.clear_)
                    print(
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
            print(Fx.normal_screen + Fx.show_cursor)
