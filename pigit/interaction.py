# -*- coding:utf-8 -*-
from typing import TYPE_CHECKING, List, Optional, Any
import os, logging
from time import sleep

from plenty import get_console
from plenty.style import Style

from .const import IS_WIN
from .tui.event_loop import EventLoop, ExitEventLoop
from .tui.screen import Screen
from .tui.widgets import SwitchWidget, RowPanelWidget, CmdRunner, ConfirmWidget
from .gitlib.options import GitOption

if TYPE_CHECKING:
    from .gitlib.model import File, Commit, Branch


Logger = logging.getLogger(__name__)

# git option handler
git = GitOption()
console = get_console()

GREEN = "#98FB98"
RED = "#F08080"
BLUE = "#6495ED"
YELLOW = "#F0E68C"


class BranchPanel(RowPanelWidget):
    def get_raw_data(self) -> List["Branch"]:
        return git.load_branches()

    def process_raw_data(self, raw_data: List["Branch"]) -> List[str]:
        processed_branches = []
        for branch in raw_data:
            if branch.is_head:
                processed_branches.append(f"* {Style(color=GREEN).render(branch.name)}")
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
            raise ExitEventLoop
        elif input_key == " ":
            local_branch = self.raw_data[cursor_row - 1]
            if local_branch.is_head:
                return

            err = git.checkout_branch(local_branch.name)
            if "error" in err:
                print(Style(color=RED).render(err), sep="")
                sleep(2)
            self.emit("update")


class StatusPanel(RowPanelWidget):
    repo_path, repo_conf = git.get_repo_info()

    def get_raw_data(self) -> List["File"]:
        return git.load_status(self.size[0], icon=True)

    def process_raw_data(self, raw_data: List[Any]) -> List[str]:
        return (
            [file.display_str for file in raw_data]
            if raw_data
            else ["No status changed."]
        )

    def print_line(self, line: str, is_cursor_row: bool) -> None:
        if self.raw_data:
            if is_cursor_row:
                print(f"{self.cursor} {line}")
            else:
                print(f"  {line}")
        else:
            # No data, print tip.
            print(line)

    def keyevent_help(self) -> str:
        return (
            "a / space: toggle storage or unstorage file.\n"
            "d: discard the file changed.\n"
            "i: append the file to `.gitignore`.\n"
            "e: open file with default editor.\n"
            "↲ : check file diff.\n"
        )

    def process_keyevent(self, input_key: str, cursor_row: int) -> Optional[int]:
        if input_key in {"a", " "}:
            git.switch_file_status(self.raw_data[cursor_row - 1], path=self.repo_path)
            self.emit("update")
        elif input_key == "d":
            if ConfirmWidget("discard all changed? [y/n]:").run():
                git.discard_file(self.raw_data[cursor_row - 1], path=self.repo_path)
            self.emit("update")
            return cursor_row - 1
        elif input_key == "i":
            git.ignore_file(self.raw_data[cursor_row - 1])
            self.emit("update")
        elif input_key == "e":
            # editor = os.environ.get("EDITOR", None)
            if editor := os.environ.get("EDITOR", None):
                CmdRunner(
                    f'{editor} "{self.raw_data[cursor_row - 1].name}"',
                    path=self.repo_path,
                )

        elif input_key == "enter":
            self.widget.set_file(self.raw_data[cursor_row - 1], self.repo_path)
            self.widget.activate()
        elif input_key == "q":
            raise ExitEventLoop


class FilePanel(RowPanelWidget):
    _file = None
    _repo_path = None

    def set_file(self, file: "File", path: str):
        if self._file != file:
            self.size = None
            self.cursor_row = 1
            self._file = file
        if self._repo_path != path:
            self._repo_path = path

    def get_raw_data(self) -> List[Any]:
        return git.load_file_diff(
            self._file.name,
            self._file.tracked,
            self._file.has_staged_change,
            path=self._repo_path,
        ).split("\n")

    def process_keyevent(self, input_key: str, cursor_row: int) -> bool:
        if input_key == "q":
            self.deactivate()

    def print_line(self, line: str, is_cursor_row: bool) -> None:
        if is_cursor_row:
            print(Style(bg_color=BLUE).render(line))
        else:
            print(line)


class CommitPanel(RowPanelWidget):
    def get_raw_data(self) -> List["Commit"]:
        branch_name = git.get_head()
        return git.load_commits(branch_name)

    def process_raw_data(self, raw_data: List[Any]) -> List[str]:
        color_data = []
        for commit in raw_data:
            c = YELLOW if commit.is_pushed() else RED
            sha = commit.sha[:7]
            msg = commit.msg
            color_data.append(Style(color=c).render(f"{sha} {msg}"))

        return color_data

    def print_line(self, line: str, is_cursor_row: bool) -> None:
        if is_cursor_row:
            print(f"{self.cursor} {line}")
        else:
            print(f"  {line}")

    def process_keyevent(self, input_key: str, cursor_row: int) -> bool:
        if input_key == "enter":
            self.widget.set_commit(self.raw_data[cursor_row - 1])
            self.widget.activate()
        elif input_key == "q":
            raise ExitEventLoop

    def keyevent_help(self) -> str:
        return "↲ : check commit diff.\n"


class CommitStatusPanel(RowPanelWidget):
    _commit = None

    def set_commit(self, commit: "Commit"):
        if self._commit != commit:
            self.size = None
            self.cursor_row = 1
            self._commit = commit

    def get_raw_data(self) -> List[Any]:
        return git.load_commit_info(self._commit.sha).split("\n")

    def print_line(self, line: str, is_cursor_row: bool) -> None:
        if is_cursor_row:
            print(Style(bg_color=BLUE).render(line))
        else:
            print(line)

    def process_keyevent(self, input_key: str, cursor_row: int) -> bool:
        if input_key == "q":
            self.deactivate()


class ModelSwitcher(SwitchWidget):
    def process_keyevent(self, key: str) -> Optional[int]:
        if key in "123456789":
            return int(key) - 1
        elif key in {"h"}:
            self.set_current(self.current - 1)
        elif key in {"l"}:
            self.set_current(self.current + 1)


def tui_main(index=None, help_wait=1.5):
    # tui interaction interface not support windows.
    if IS_WIN:
        console.echo("`Terminal interaction not support windows now.`<#FF0000>")
        return

    if not git.get_repo_info()[0]:
        console.echo("`Please run in a git repo dir.`<tomato>")
        return

    status = StatusPanel(widget=FilePanel(), help_wait=help_wait)
    commit = CommitPanel(widget=CommitStatusPanel(), help_wait=help_wait)
    branch = BranchPanel(help_wait=help_wait)
    switcher = ModelSwitcher(sub_widgets=[status, commit, branch])

    if index:
        start_idx = index
        switcher.set_current(int(start_idx) - 1)

    screen = Screen(switcher)
    main_loop = EventLoop(screen)
    main_loop.set_input_timeouts(0.125)
    main_loop.run()
