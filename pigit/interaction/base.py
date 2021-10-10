# -*- coding:utf-8 -*-

from abc import ABC, abstractmethod
from typing import Optional

from ..common import Fx, TermColor, exec_cmd, shorten, get_width
from ..common.singleton import Singleton
from ..keyevent import get_keyevent_obj
from .model import File


class InteractionError(Exception):
    pass


class DataHandle(object, metaclass=Singleton):
    def __init__(self, use_color: bool):
        self.use_color = use_color

    def get_status(self, max_width: int, ident: int = 2) -> list[File]:
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

    def get_file_diff(
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


class _Interaction(ABC):
    def __init__(
        self,
        use_color: bool = True,
        cursor: Optional[str] = None,
        help_wait: float = 1.5,
        debug: bool = False,
    ) -> None:
        self.use_color = use_color

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

    @abstractmethod
    def process(self):
        """Processing data, and subclasses determine how to behave."""

    @abstractmethod
    def run(self):
        """Run method."""
