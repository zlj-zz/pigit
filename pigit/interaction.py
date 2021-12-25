# -*- coding:utf-8 -*-
import os, sys
from time import sleep
from typing import Optional, Any

from .tui.loop import Loop, ExitLoop
from .tui.screen import Screen
from .tui.widgets import SwitchWidget, RowPanelWidget, CmdRunner, ConfirmWidget
from .common import Color, Fx, render_str
from .common.git_utils import (
    # info method
    load_branches,
    load_status,
    load_file_diff,
    load_commits,
    load_commit_info,
    current_head,
    # option method
    switch_file_status,
    discard_file,
    checkout_branch,
)
from .common.git_model import File, Commit, Branch


class BranchPanel(RowPanelWidget):
    def get_raw_data(self) -> list[Branch]:
        return load_branches()

    def process_raw_data(self, raw_data: list[Branch]) -> list[str]:
        processed_branches = []
        for branch in raw_data:
            if branch.is_head:
                processed_branches.append(
                    f"* {Color.fg('#98FB98')}{branch.name}{Fx.rs}"
                )
            else:
                processed_branches.append(f"  {branch.name}")

        return processed_branches

    def print_line(self, line: str, is_cursor_row: bool) -> None:
        if is_cursor_row:
            print(f"{self.cursor} {line}")
        else:
            print(f"  {line}")

    def keyevent_help(self) -> str:
        return "space: switch current branch.\n"

    def process_keyevent(self, input_key: str, cursor_row: int) -> bool:
        if input_key == "q":
            raise ExitLoop
        elif input_key == " ":
            local_branch = self.raw_data[cursor_row - 1]
            if local_branch.is_head:
                return

            err = checkout_branch(local_branch.name)
            if "error" in err:
                print(Color.fg("#FF0000"), err, Fx.rs, sep="")
                sleep(2)
            self.emit("update")


class StatusPanel(RowPanelWidget):
    def get_raw_data(self) -> list[File]:
        return load_status(self.size[0])

    def process_raw_data(self, raw_data: list[Any]) -> list[str]:
        if not raw_data:
            return ["No status changed."]
        l = [file.display_str for file in raw_data]
        return l

    def print_line(self, line: str, is_cursor_row: bool) -> None:
        if self.raw_data:
            if is_cursor_row:
                print("{} {}".format(self.cursor, line))
            else:
                print("  " + line)
        else:
            # No data, print tip.
            print(line)

    def keyevent_help(self) -> str:
        return (
            "a / space: toggle storage or unstorage file.\n"
            "d: discard the file changed.\n"
            "e: open file with default editor.\n"
            "↲ : check file diff.\n"
        )

    def process_keyevent(self, input_key: str, cursor_row: int) -> bool:
        if input_key in ["a", " "]:
            switch_file_status(self.raw_data[cursor_row - 1])
            self.emit("update")
        elif input_key == "d":
            if ConfirmWidget("discard all changed? [y/n]:").run():
                # if confirm("discard all changed? [y/n]:"):
                discard_file(self.raw_data[cursor_row - 1])
            self.emit("update")
        elif input_key == "e":
            # editor = os.environ.get("EDITOR", None)
            if editor := os.environ.get("EDITOR", None):
                CmdRunner('{} "{}"'.format(editor, self.raw_data[cursor_row - 1].name))
            else:
                # No default editor to open file.
                pass
        elif input_key == "enter":
            # TODO: how to do ?
            self.widget.set_file(self.raw_data[cursor_row - 1])
            self.widget.activate()
        elif input_key == "q":
            raise ExitLoop


class FilePanel(RowPanelWidget):
    _file = None

    def set_file(self, file: File):
        if self._file != file:
            self.size = None
            self.cursor_row = 1
            self._file = file

    def get_raw_data(self) -> list[Any]:
        return load_file_diff(
            self._file.name, self._file.tracked, self._file.has_staged_change
        ).split("\n")

    def process_keyevent(self, input_key: str, cursor_row: int) -> bool:
        if input_key == "q":
            self.deactivate()

    def print_line(self, line: str, is_cursor_row: bool) -> None:
        if is_cursor_row:
            print("{}{}{}".format(Color.bg("#6495ED"), line, Fx.reset))
        else:
            print(line)


class CommitPanel(RowPanelWidget):
    def get_raw_data(self) -> list[Commit]:
        branch_name = current_head()
        return load_commits(branch_name)

    def process_raw_data(self, raw_data: list[Any]) -> list[str]:
        color_data = []
        pushed_c = Color.fg("#F0E68C")
        unpushed_c = Color.fg("#F08080")
        for commit in raw_data:
            c = pushed_c if commit.is_pushed() else unpushed_c
            sha = commit.sha[:7]
            msg = commit.msg
            color_data.append(f"{c}{sha} {msg}{Fx.rs}")

        return color_data

    def print_line(self, line: str, is_cursor_row: bool) -> None:
        if is_cursor_row:
            print(f"{self.cursor} {line}")
        else:
            print("  " + line)

    def process_keyevent(self, input_key: str, cursor_row: int) -> bool:
        if input_key == "q":
            raise ExitLoop

        elif input_key == "enter":
            self.widget.set_commit(self.raw_data[cursor_row - 1])
            self.widget.activate()

    def keyevent_help(self) -> str:
        return "↲ : check commit diff.\n"


class CommitStatusPanel(RowPanelWidget):
    _commit = None

    def set_commit(self, commit: Commit):
        if self._commit != commit:
            self.size = None
            self.cursor_row = 1
            self._commit = commit

    def get_raw_data(self) -> list[Any]:
        return load_commit_info(self._commit.sha).split("\n")

    def print_line(self, line: str, is_cursor_row: bool) -> None:
        if is_cursor_row:
            print("{}{}{}".format(Color.bg("#6495ED"), line, Fx.reset))
        else:
            print(line)

    def process_keyevent(self, input_key: str, cursor_row: int) -> bool:
        if input_key == "q":
            self.deactivate()


class ModelSwitcher(SwitchWidget):
    def process_keyevent(self, key: str) -> Optional[int]:
        if key in "123456789":
            return int(key) - 1


def main(args=None):
    # tui interaction interface not support windows.
    if sys.platform.lower().startswith("win"):
        print(render_str("`Terminal interaction not support windows now.`<#FF0000>"))
        return

    status = StatusPanel(widget=FilePanel())
    commit = CommitPanel(widget=CommitStatusPanel())
    branch = BranchPanel()
    switcher = ModelSwitcher(sub_widgets=[status, commit, branch])

    if args:
        start_idx = args[0]
        switcher.set_current(int(start_idx) - 1)

    screen = Screen(switcher)
    main_loop = Loop(screen)
    main_loop.set_input_timeouts(0.125)
    main_loop.run()
