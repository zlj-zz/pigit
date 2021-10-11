# -*- coding:utf-8 -*-

import re
import time
from math import ceil
from abc import ABC, abstractmethod
from shutil import get_terminal_size
from typing import Optional, Any

from ..common import Fx, TermColor, exec_cmd, shorten, get_width, color_print
from ..common.singleton import Singleton
from ..keyevent import get_keyevent_obj
from ..gitinfo import REPOSITORY_PATH
from .model import File, Commit


class InteractionError(Exception):
    pass


class DataHandle(object, metaclass=Singleton):
    def __init__(self, use_color: bool):
        self.use_color = use_color

    def current_head(self):
        """Get current repo head.

        return a branch name or a commit sha string.
        """
        _, res = exec_cmd("git symbolic-ref -q --short HEAD")
        return res.rstrip()

    def load_status(self, max_width: int, ident: int = 2) -> list[File]:
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
            if not file.strip():
                # skip blank line.
                continue
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

    def load_file_diff(
        self, file: str, tracked: bool = True, cached: bool = False, plain: bool = False
    ) -> str:
        """Gets the modification of the file.

        Args:
            file (str): file path relative to git.
            tracked (bool, optional): Defaults to True.
            cached (bool, optional): Defaults to False.
            plain (bool, optional): Whether need color. Defaults to False.

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

        if "->" in file:  # rename status.
            file = file.split("->")[-1].strip()

        err, res = exec_cmd(
            command.format(plain=_plain, cached=_cached, tracked=_tracked, file=file)
        )
        if err:
            return "Can't get diff."
        return res.rstrip()

    def load_commits(
        self, branch_name: str, limit: bool = True, filter_path: str = ""
    ) -> list[Commit]:
        """Get the all commit of a given branch.

        Args:
            branch_name (str): want branch name.
            limit (bool): Whether to get only the latest 300.
            filter_path (str): filter dir path, default is empty.
        """

        passed_first_pushed_commit = False
        command = "git merge-base %s %s@{u}" % (branch_name, branch_name)
        _, resp = exec_cmd(command)
        first_pushed_commit = resp.strip()

        if not first_pushed_commit:
            passed_first_pushed_commit = True

        commits: list[Commit] = []

        # Generate git command.
        limit_flag = "-300" if limit else ""
        filter_flag = f"--follow -- {filter_path}" if filter_path else ""
        command = f'git log {branch_name} --oneline --pretty=format:"%H|%at|%aN|%d|%p|%s" {limit_flag} --abbrev=20 --date=unix {filter_flag}'
        err, resp = exec_cmd(command)

        # Process data.
        lines = resp.split("\n")
        if not err:
            for line in lines:
                split_ = line.split("|")

                sha = split_[0]
                unix_timestamp = int(split_[1])
                author = split_[2]
                extra_info = (split_[3]).strip()
                # parent_hashes = split_[4]
                message = "|".join(split_[5:])

                tag = []
                if extra_info:
                    _re = re.compile(r"tag: ([^,\\]+)")
                    match = _re.search(extra_info)
                    if match:
                        tag.append(match[1])

                if sha == first_pushed_commit:
                    passed_first_pushed_commit = True
                status = {True: "unpushed", False: "pushed"}[
                    not passed_first_pushed_commit
                ]

                commit_ = Commit(
                    sha=sha,
                    msg=message,
                    author=author,
                    unix_timestamp=unix_timestamp,
                    status=status,
                    extra_info=extra_info,
                    tag=tag,
                )
                commits.append(commit_)

        return commits

    def load_commit_info(
        self, commit_sha: str, file_name: str = "", plain: bool = False
    ) -> str:
        """Gets the change of a file or all in a given commit.

        Args:
            commit_sha: commit id.
            file_name: file name(include full path).
            plain: whether has color.
        """

        color_str = "never" if plain else "always"

        command = "git show --color=%s %s %s" % (color_str, commit_sha, file_name)
        _, resp = exec_cmd(command)
        return resp.rstrip()


# whether already in interactive mode.
_Interaction_Starting = False


class _Interaction(ABC):
    def __init__(
        self,
        use_color: bool = True,
        cursor: Optional[str] = None,
        help_wait: float = 1.5,
        is_sub: bool = False,  # whether is sub page.
        debug: bool = False,
        **kwargs,
    ) -> None:
        self.use_color = use_color
        self._is_sub = is_sub

        if not cursor:
            self.cursor = "→"
        elif len(cursor) == 1:
            if get_width(ord(cursor)) == 1:
                self.cursor = cursor
            else:
                self.cursor = "→"
                print("When displayed, it will occupy more than one character.")
        else:
            self.cursor = "→"
            print("The cursor symbol entered is not supported.")

        self.help_wait = help_wait
        self._min_height = 8
        self._min_width = 60
        self._debug = debug

        # Whether can into interactive.
        try:
            _keyevent_class = get_keyevent_obj()
        except NameError:
            raise InteractionError(
                "This behavior is not supported in the current system."
            )
        self._keyevent = _keyevent_class()

        self._data_handle = DataHandle(use_color)

        for key, value in kwargs.items():
            setattr(self, "_ex_{}".format(key), value)

    @abstractmethod
    def process_keyevent(self, input_key: str, cursor_row: int, data: Any) -> bool:
        """Handles keyboard events other than movement.

        Args:
            input_key (str): keyboard string.
            cursor_row (int): current line.
            data (Any): raw data.

        Returns:
            bool: whether need refresh data.
        """

    @abstractmethod
    def keyevent_help(self) -> str:
        """Get extra keyevent help message.

        Returns:
            str: help message string.
        """

    @abstractmethod
    def get_raw_data(self) -> list[Any]:
        """How to get the raw data."""

    def process_raw_data(
        self, raw_data: list[str], width: int
    ) -> list[tuple[str, int]]:
        new_list = []
        for line in raw_data:
            text = Fx.uncolor(line)
            count = 0
            for ch in text:
                count += get_width(ord(ch))
            # [float] is to solve the division of python2 without
            # retaining decimal places.
            new_list.append((line, ceil(count / width) - 1))
        return new_list

    @abstractmethod
    def print_line(self, line: str, is_cursor_row: bool) -> None:
        """How to output one line.

        May has some different when current line is cursor line.
        Support to process cursor line specially.
        """

    def run(self, *args):
        """Run method."""
        global _Interaction_Starting

        # Make sure run at a git repo dir.
        if not REPOSITORY_PATH:
            color_print("Current path is not a git repository.", TermColor.Red)
            return

        self.width, self.height = width, height = get_terminal_size()

        # Make sure have enough space.
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
        display_range: list = [1, height - 1]  # allow display row range.

        stopping: bool = False  # Stop flag.
        refresh: bool = False  # refresh data flag.

        raw_data: list[Any] = self.get_raw_data()
        self.raw_data = raw_data
        if not raw_data:
            print("The work tree is clean and there is nothing to operate.")
            return
        show_data = self.process_raw_data(raw_data, width)

        extra = 0  # Extra occupied row.

        # Into new term page.
        try:
            if not _Interaction_Starting:
                _Interaction_Starting = True
                print(Fx.alt_screen + Fx.hide_cursor)
                #  try hook window resize event.
                self._keyevent.signal_init()

            # Start interactive.
            while not stopping:
                if refresh:
                    refresh = False
                    raw_data: list[Any] = self.get_raw_data()
                    self.raw_data = raw_data
                    show_data = self.process_raw_data(raw_data, width)

                print(Fx.clear_)

                # check whether have status.
                if not raw_data:
                    print("The work tree is clean and there is nothing to operate.")
                    time.sleep(1)
                    return

                while cursor_row < display_range[0]:
                    display_range = [i - 1 for i in display_range]
                while cursor_row + extra > display_range[1]:
                    display_range = [i + 1 for i in display_range]

                extra = 0  # Return to zero and accumulate again.

                # Print needed display part.
                for index, item in enumerate(show_data, start=1):
                    line, each_extra = item
                    if display_range[0] <= index <= display_range[1] - extra:
                        self.print_line(line, index == cursor_row)
                        extra += each_extra

                input_key = self._keyevent.sync_get_input()
                if input_key in ["q", "escape"]:
                    # exit.
                    stopping = True
                elif input_key in ["j", "down"]:
                    # select pre file.
                    cursor_row += 1
                    cursor_row = min(cursor_row, len(show_data))
                elif input_key in ["k", "up"]:
                    # select next file.
                    cursor_row -= 1
                    cursor_row = max(cursor_row, 1)
                elif input_key in ["J"]:
                    # scroll down 5 lines.
                    cursor_row += 5
                    cursor_row = min(cursor_row, len(show_data))
                elif input_key in ["K"]:
                    # scroll up 5 line
                    cursor_row -= 5
                    cursor_row = max(cursor_row, 1)

                elif input_key in "0123456789":
                    return int(input_key)
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
                    width, height = new_width, new_height
                    # get new display range.
                    display_range[1] += line_diff
                    show_data = self.process_raw_data(raw_data, width)
                elif input_key in ["?", "h"]:
                    print(Fx.clear_)
                    print(
                        (
                            "k / ↑: select previous line.\n"
                            "j / ↓: select next line.\n"
                            "J: Scroll down 5 lines.\n"
                            "K: Scroll down 5 lines.\n"
                            "? / h : show help, wait {}s and exit.\n"
                            + self.keyevent_help()
                        ).format(self.help_wait)
                    )
                    if self.help_wait == 0:
                        self._keyevent.sync_get_input()
                    else:
                        time.sleep(self.help_wait)
                else:
                    refresh = self.process_keyevent(input_key, cursor_row, raw_data)

        except KeyboardInterrupt:
            pass
        finally:
            # Whatever, unregister signal event and restore terminal at last.
            if _Interaction_Starting and not self._is_sub:
                _Interaction_Starting = False
                self._keyevent.signal_restore()
                print(Fx.normal_screen + Fx.show_cursor, end="")
