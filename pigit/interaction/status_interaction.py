# -*- coding:utf-8 -*-

import os

from ..common import Fx, Color, exec_cmd, run_cmd, confirm
from .base import _Interaction, InteractionError
from .model import File


class InteractiveShowFile(_Interaction):
    def keyevent_help(self) -> str:
        return ""

    def process_keyevent(self):
        pass

    def get_raw_data(self) -> list[str]:
        return self._data_handle.load_file_diff(
            self._ex_file.name,
            self._ex_file.tracked,
            self._ex_file.has_staged_change,
            not self.use_color,
        ).split("\n")

    def print_line(self, line: str, is_cursor_row: bool) -> None:
        if is_cursor_row:
            print("{}{}{}".format(Color.bg("#6495ED"), line, Fx.reset))
        else:
            print(line)


class InteractiveStatus(_Interaction):
    """Interactive operation git tree status."""

    def keyevent_help(self) -> str:
        return (
            "a / space: toggle storage or unstorage file.\n"
            "d: discard the file changed.\n"
            "e: open file with default editor.\n"
            "↲ : check file diff.\n"
        )

    def process_keyevent(
        self, input_key: str, cursor_row: int, data: list[File]
    ) -> bool:
        refresh = False
        if input_key in ["a", "space"]:
            self.process_f(data[cursor_row - 1], "switch")
            refresh = True
        elif input_key == "d":
            self.process_f(data[cursor_row - 1], "discard")
            refresh = True
        elif input_key == "e":
            editor = os.environ.get("EDITOR", None)
            if editor:
                run_cmd('{} "{}"'.format(editor, data[cursor_row - 1].name))
                refresh = True
            else:
                # No default editor to open file.
                pass
        elif input_key == "enter":
            InteractiveShowFile(
                self.use_color,
                self.cursor,
                self.help_wait,
                True,
                self._debug,
                file=data[cursor_row - 1],
            ).run()

        return refresh

    def process_f(self, file: File, flag: str) -> None:
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

    def get_raw_data(self) -> list[File]:
        return self._data_handle.load_status(self.width)

    def process_raw_data(
        self, raw_data: list[File], width: int
    ) -> list[tuple[str, int]]:
        l = [file.display_str for file in raw_data]
        return super().process_raw_data(l, width)

    def print_line(self, line: str, is_cursor_row: bool) -> None:
        if is_cursor_row:
            print("{} {}".format(self.cursor, line))
        else:
            print("  " + line)
