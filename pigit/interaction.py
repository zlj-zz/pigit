# -*- coding:utf-8 -*-
import os
import re
from typing import Optional, Any

from .tui.loop import Loop, ExitLoop
from .tui.screen import Screen
from .tui.widgets import SwitchWidget, RowPanelWidget
from .tui.model import File, Commit

from .common import shorten, render_str, exec_cmd, run_cmd, confirm, Color, Fx


class StatusPanel(RowPanelWidget):
    def get_raw_data(self) -> list[File]:
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

            ident = 2
            display_name = shorten(name, self.size[0] - 3 - ident)
            # color full command.
            display_str = render_str(
                f"`{staged_change}`<{'bad' if has_no_staged_change else'right'}>`{unstaged_change}`<{'bad' if unstaged_change!=' ' else'right'}> {display_name}"
            )

            file_ = File(
                name=name,
                display_str=display_str,
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

    def process_raw_data(self, raw_data: list[Any]) -> list[str]:
        if not raw_data:
            return ["No status changed."]
        l = [file.display_str for file in raw_data]
        return l

    def print_line(self, line: str, is_cursor_row: bool) -> None:
        if is_cursor_row:
            print("{} {}".format(self.cursor, line))
        else:
            print("  " + line)

    def keyevent_help(self) -> str:
        return (
            "a / space: toggle storage or unstorage file.\n"
            "d: discard the file changed.\n"
            "e: open file with default editor.\n"
            "↲ : check file diff.\n"
        )

    def process_keyevent(self, input_key: str, cursor_row: int) -> bool:
        if input_key in ["a", " "]:
            self.modify_file_status(self.raw_data[cursor_row - 1], "switch")
            self.emit("update")
        elif input_key == "d":
            self.modify_file_status(self.raw_data[cursor_row - 1], "discard")
            self.emit("update")
        elif input_key == "e":
            # editor = os.environ.get("EDITOR", None)
            if editor := os.environ.get("EDITOR", None):
                run_cmd('{} "{}"'.format(editor, self.raw_data[cursor_row - 1].name))
            else:
                # No default editor to open file.
                pass
        elif input_key == "enter":
            # TODO: how to do ?
            self.widget.set_file(self.raw_data[cursor_row - 1])
            self.widget.activate()
            pass
        elif input_key == "q":
            raise ExitLoop

    def modify_file_status(self, file: File, flag: str) -> None:
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
            # print(Term.clear_screen)
            if confirm("discard all changed? [y/n]:"):
                if file.tracked:
                    exec_cmd("git checkout -- {}".format(file.name))
                else:
                    os.remove(os.path.join(file.name))


class FilePanel(RowPanelWidget):
    _file = None

    def set_file(self, file: File):
        if self._file != file:
            self.size = None
            self.cursor_row = 1
            self._file = file

    def get_raw_data(self) -> list[Any]:
        """Gets the modification of the file.

        Args:
            file (str): file path relative to git.
            tracked (bool, optional): Defaults to True.
            cached (bool, optional): Defaults to False.
            plain (bool, optional): Whether need color. Defaults to False.

        Returns:
            (str): change string.
        """
        if not self._file:
            raise

        name = self._file.name
        tracked = self._file.tracked
        cached = self._file.has_staged_change
        plain = False

        command = "git diff --submodule --no-ext-diff {plain} {cached} {tracked} {name}"

        _plain = "--color=never" if plain else "--color=always"

        _cached = "--cached" if cached else ""

        _tracked = "--no-index -- /dev/null" if not tracked else "--"

        if "->" in name:  # rename status.
            name = name.split("->")[-1].strip()

        err, res = exec_cmd(
            command.format(plain=_plain, cached=_cached, tracked=_tracked, name=name)
        )
        if err:
            return "Can't get diff."
        return res.rstrip().split("\n")

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
        _, res = exec_cmd("git symbolic-ref -q --short HEAD")
        branch_name = res.rstrip()

        #
        limit = None
        filter_path = None
        #
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

        if err:
            return commits  # current is empty list.

        # Process data.
        for line in resp.split("\n"):
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
                if match := _re.search(extra_info):
                    tag.append(match[1])

            if sha == first_pushed_commit:
                passed_first_pushed_commit = True
            status = {True: "unpushed", False: "pushed"}[not passed_first_pushed_commit]

            commit_ = Commit(
                sha=sha,
                msg=shorten(message, self.size[0] - 2),
                author=author,
                unix_timestamp=unix_timestamp,
                status=status,
                extra_info=extra_info,
                tag=tag,
            )
            commits.append(commit_)

        return commits

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
            print("{} {}".format(self.cursor, line))
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
        """Gets the change of a file or all in a given commit.

        Args:
            commit_sha: commit id.
            file_name: file name(include full path).
            plain: whether has color.
        """
        commit_sha = self._commit.sha
        plain = False
        file_name = ""

        color_str = "never" if plain else "always"

        command = "git show --color=%s %s %s" % (color_str, commit_sha, file_name)
        _, resp = exec_cmd(command)
        return resp.rstrip().split("\n")

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
    status = StatusPanel(widget=FilePanel())
    commit = CommitPanel(widget=CommitStatusPanel())
    switcher = ModelSwitcher(sub_widgets=[status, commit])

    if args:
        start_idx = args[0]
        switcher.set_current(int(start_idx) - 1)

    screen = Screen(switcher)
    main_loop = Loop(screen)
    main_loop.set_input_timeouts(0.125)
    main_loop.run()
