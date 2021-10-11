# -*- coding:utf-8 -*-

from ..common import Fx, Color, shorten
from .base import _Interaction
from .model import Commit


class InteractiveShowCommitInfo(_Interaction):
    def keyevent_help(self) -> str:
        return ""

    def process_keyevent(self, input_key: str, cursor_row: int, data) -> bool:
        pass

    def get_raw_data(self) -> list[str]:
        return self._data_handle.load_commit_info(
            self._ex_commit.sha,
        ).split("\n")

    def print_line(self, line: str, is_cursor_row: bool) -> None:
        if is_cursor_row:
            print("{}{}{}".format(Color.bg("#6495ED"), line, Fx.reset))
        else:
            print(line)


class InteractiveCommit(_Interaction):
    def keyevent_help(self) -> str:
        return "↲ : check commit diff.\n"

    def process_keyevent(
        self, input_key: str, cursor_row: int, data: list[Commit]
    ) -> bool:
        if input_key == "enter":
            InteractiveShowCommitInfo(
                self.use_color,
                self.cursor,
                self.help_wait,
                True,
                self._debug,
                commit=data[cursor_row - 1],
            ).run()

    def get_raw_data(self) -> list[Commit]:
        current = self._data_handle.current_head()
        return self._data_handle.load_commits(current)

    def process_raw_data(
        self, raw_data: list[Commit], width: int
    ) -> list[tuple[str, int]]:
        color_data = []
        pushed_c = Color.fg("#F0E68C")
        unpushed_c = Color.fg("#F08080")
        for commit in raw_data:
            c = pushed_c if commit.is_pushed() else unpushed_c
            sha = commit.sha[:7]
            msg = shorten(commit.msg, width - 2)
            color_data.append(f"{c}{sha} {msg}{Fx.rs}")

        return super().process_raw_data(color_data, width)

    def print_line(self, line: str, is_cursor_row: bool) -> None:
        if is_cursor_row:
            print("{} {}".format(self.cursor, line))
        else:
            print("  " + line)
