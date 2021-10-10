# -*- coding:utf-8 -*-

import os
import time
from math import ceil
from shutil import get_terminal_size

from ..common import (
    Fx,
    Color,
    TermColor,
    color_print,
    exec_cmd,
    run_cmd,
    confirm,
    get_width,
)
from ..gitinfo import REPOSITORY_PATH
from .base import _Interaction, InteractionError
from .model import File


class InteractiveShowFile(_Interaction):
    def process(self):
        pass

    def run(self, file_obj: File):
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
        diff_raw = self._data_handle.get_file_diff(
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

            input_key = self._keyevent.sync_get_input()
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
                    raise InteractionError(
                        "The minimum size of terminal should be {0} x {1}.".format(
                            self._min_width, self._min_height
                        )
                    )
                # get size diff, reassign.
                line_diff = new_height - height
                width, height = new_width, new_height
                # get new display range.
                display_range[1] += line_diff
                diff_ = _process_diff(diff_raw, width)
            elif input_key in ["?", "h"]:
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
                    self._keyevent.sync_get_input()
                else:
                    time.sleep(self.help_wait)
            else:
                continue
        pass


class InteractiveStatus(_Interaction):
    """Interactive operation git tree status."""

    def process(self, file: File, flag: str) -> None:
        """Process file to change the status.

        Args:
            file (File): One processed file.
        """

        if flag == "switch":
            if file.has_merged_conflicts or file.has_inline_merged_conflicts:
                pass
            elif file.has_unstaged_change:
                exec_cmd("git add -- {}".format(file.name))
            elif file.has_staged_change:
                if file.tracked:
                    exec_cmd("git reset HEAD -- {}".format(file.name))
                else:
                    exec_cmd("git rm --cached --force -- {}".format(file.name))

        elif flag == "discard":
            print(Fx.clear_)
            if confirm("discard all changed? [y/n]:"):
                if file.tracked:
                    exec_cmd("git checkout -- {}".format(file.name))
                else:
                    os.remove(os.path.join(file.name))

    def run(self, *args):
        """Interactive main method."""

        if not REPOSITORY_PATH:
            color_print("Current path is not a git repository.", TermColor.Red)
            return

        width, height = get_terminal_size()
        if height < self._min_height or width < self._min_width:
            raise InteractionError(
                "The minimum size of terminal should be {0} x {1}.".format(
                    self._min_width, self._min_height
                )
            )

        if self._debug:  # debug show.
            print(Fx.clear_)
            print(width, height)
            time.sleep(1.5)

        # Initialize.
        cursor_row: int = 1
        cursor_icon: str = self.cursor
        display_range: list = [1, height - 1]

        stopping: bool = False

        file_items = self._data_handle.get_status(width)
        if not file_items:
            print("The work tree is clean and there is nothing to operate.")
            return

        # Into new term page.
        print(Fx.alt_screen + Fx.hide_cursor)
        try:
            #  try hook window resize event.
            self._keyevent.signal_init()

            # Start interactive.
            while not stopping:
                print(Fx.clear_)

                # check whether have status.
                if not file_items:
                    print("The work tree is clean and there is nothing to operate.")
                    time.sleep(1)
                    return

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

                input_key = self._keyevent.sync_get_input()
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
                elif input_key in ["a", "space"]:
                    self.process(file_items[cursor_row - 1], "switch")
                    file_items = self._data_handle.get_status(width)
                elif input_key == "d":
                    self.process(file_items[cursor_row - 1], "discard")
                    file_items = self._data_handle.get_status(width)
                elif input_key == "e":
                    editor = os.environ.get("EDITOR", None)
                    if editor:
                        run_cmd(
                            '{} "{}"'.format(editor, file_items[cursor_row - 1].name)
                        )
                        file_items = self._data_handle.get_status(width)
                    else:
                        # No default editor to open file.
                        pass
                elif input_key == "enter":
                    InteractiveShowFile(
                        self.use_color, self.cursor, self.help_wait, self._debug
                    ).run(file_items[cursor_row - 1])
                elif input_key == "windows resize":
                    # get new term height.
                    new_width, new_height = get_terminal_size()
                    if new_height < self._min_height or new_width < self._min_width:
                        raise InteractionError(
                            "The minimum size of terminal should be {0} x {1}.".format(
                                self._min_width, self._min_height
                            )
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
                        self._keyevent.sync_get_input()
                    else:
                        time.sleep(self.help_wait)
                else:
                    # If not needed input key, skip and wait.
                    continue
        except KeyboardInterrupt:
            pass
        finally:
            # Whatever, unregister signal event and restore terminal at last.
            self._keyevent.signal_restore()
            print(Fx.normal_screen + Fx.show_cursor)
