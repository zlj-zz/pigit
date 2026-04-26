# -*- coding: utf-8 -*-
"""
Module: pigit/git/repo_cd_picker.py
Description: TTY picker for ``pigit repo cd --pick``.
Author: Zev
Date: 2026-04-20
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Sequence

from pigit.ext.executor import WAITING

from pigit.termui import (
    Application,
    Column,
    Component,
    ComponentRoot,
    ExitEventLoop,
    HelpPanel,
    InputLine,
    ItemSelector,
    StatusBar,
    Popup,
    keys,
)
from pigit.termui._picker import (
    PICK_EXIT_CTRL_C,
    PickerHeader,
    PickerMode,
    PickerRow,
    PickerState,
    apply_picker_filter,
    picker_terminal_ok,
)
from pigit.termui.tty_io import terminal_size, tty_ok

if TYPE_CHECKING:
    from pigit.ext.executor import Executor

REPO_CD_NO_TTY_MSG = (
    "`pigit repo cd --pick`<error> needs an interactive terminal.\n"
    "Use an explicit managed repo name in scripts and CI, or run "
    "`pigit repo cd --pick` only in a real terminal.\n"
    "See `pigit repo cd -h`."
)

_REPO_CD_TERMINAL_TOO_SMALL_MSG = (
    "Terminal is too small for `pigit repo cd --pick` (need room for a fixed header, "
    "at least one list row, and a footer line). Enlarge the window or use a "
    "non-interactive repo name."
)

EMPTY_MANAGED_REPOS_MSG = "No managed repos; use `pigit repo add`."


def run_repo_cd_picker(
    rows: Sequence[PickerRow],
    executor: "Executor",
    *,
    initial_filter: str = "",
    pick_alt_screen: bool = False,
) -> tuple[int, Optional[str]]:
    """
    Interactive repo directory picker; on confirm runs shell ``cd`` + ``exec $SHELL``.

    Requires a real TTY (same gate as :func:`tty_ok`).

    Returns:
        ``(exit_code, message)``. ``0`` with ``None`` after successful ``cd`` or user quit.
    """
    if not rows:
        return 1, EMPTY_MANAGED_REPOS_MSG
    if not tty_ok():
        return 1, REPO_CD_NO_TTY_MSG

    title = (
        "pigit repo cd --pick  "
        "[j/k scroll  Enter cd  / filter  q/Esc quit  Ctrl+C abort]"
    )

    rendered = [f"{r.title}  {r.detail}" for r in rows]

    class _RepoCdPickerApp(Application):
        BINDINGS = [
            ("Q", "quit"),
            ("?", "toggle_help"),
        ]

        def __init__(self) -> None:
            super().__init__(input_takeover=True, alt=True)
            self._state = PickerState()
            self._mode = PickerMode.BROWSE
            self._initial_filter = initial_filter
            self._rows = rows
            self._filtered_rows = list(rows)
            self._last_needle: str = ""

        def build_root(self) -> Component:
            self._header = PickerHeader(title)
            self._list = ItemSelector(
                content=list(rendered),
                on_selection_changed=lambda idx: self._state.selected_idx.set(idx),
            )
            self._status = StatusBar(self._state.status_text)
            self._input = InputLine(
                prompt="/",
                visible=False,
                on_value_changed=self._on_filter_value_changed,
                on_submit=self._on_input_submit,
                on_cancel=self._on_input_cancel,
            )
            self._layout = Column(
                [self._header, self._list, self._status, self._input],
                heights=[3, "flex", 1, 0],
            )
            return self._layout

        def setup_root(self, root: ComponentRoot) -> None:
            self._loop.set_input_timeouts(0.125)
            root.show_toast(
                "j/k scroll, Enter cd, / filter, ? help",
                duration=3.0,
            )
            self._help_panel = HelpPanel()
            self._help_popup = Popup(
                self._help_panel,
                session_owner=root,
                exit_key=keys.KEY_ESC,
            )
            self._state.selected_idx.subscribe(self._update_status)
            self._update_status(0)

            if self._initial_filter:
                self._input.set_value(self._initial_filter)
                self._enter_filter()
                self._apply_filter()

        def after_start(self) -> None:
            _, term_rows = terminal_size()
            if not picker_terminal_ok(term_rows):
                self.quit(
                    exit_code=1,
                    result_message=_REPO_CD_TERMINAL_TOO_SMALL_MSG,
                )

        # --- Event handling ---

        def on_key(self, key: str) -> None:
            if self._mode == PickerMode.FILTER:
                if key == "ctrl c":
                    raise ExitEventLoop(
                        "quit", exit_code=PICK_EXIT_CTRL_C, result_message=None
                    )
                self._input.on_key(key)
                return
            self._on_browse(key)

        def _on_browse(self, key: str) -> None:
            if key in ("j", keys.KEY_DOWN):
                self._list.next()
            elif key in ("k", keys.KEY_UP):
                self._list.previous()
            elif key == "enter":
                self._execute_selected()
            elif key == "/":
                self._enter_filter()
            elif key in ("q", keys.KEY_ESC):
                self.quit()
            elif key == "?":
                self._show_preview()

        # --- Filter mode ---

        def _on_filter_value_changed(self, text: str) -> None:
            self._state.filter_text.set(text)
            self._apply_filter()

        def _enter_filter(self) -> None:
            self._mode = PickerMode.FILTER
            self._input.set_visible(True)
            self._layout.set_heights([3, "flex", 1, 1])
            self.resize(self._loop.get_term_size())

        def _exit_filter(self) -> None:
            self._mode = PickerMode.BROWSE
            self._input.set_visible(False)
            self._layout.set_heights([3, "flex", 1, 0])
            self.resize(self._loop.get_term_size())

        def _apply_filter(self) -> None:
            needle = self._input.value
            if needle == self._last_needle:
                return
            self._last_needle = needle
            filtered = apply_picker_filter(self._rows, needle)
            self._filtered_rows = filtered
            self._list.set_content([f"{r.title}  {r.detail}" for r in filtered])
            self._list.curr_no = 0
            self._state.selected_idx.set(0)
            self._update_status(0)

        def _on_input_submit(self, value: str) -> None:
            self._exit_filter()

        def _on_input_cancel(self) -> None:
            self._exit_filter()
            self._input.clear()

        # --- Business logic ---

        def _execute_selected(self) -> None:
            idx = self._list.curr_no
            if idx < 0 or idx >= len(self._filtered_rows):
                return
            path = self._filtered_rows[idx].ref
            assert isinstance(path, str)
            raise ExitEventLoop("done", exit_code=0, result_message=path)

        def _show_preview(self) -> None:
            idx = self._list.curr_no
            if idx < 0 or idx >= len(self._filtered_rows):
                return
            path = self._filtered_rows[idx].ref
            assert isinstance(path, str)
            self._status.set_text(f"path: {path}")

        def _update_status(self, idx: int) -> None:
            n = len(self._list.content)
            vp = self._list.visible_row_count
            if n > vp:
                lo = self._list.viewport_start + 1
                hi = min(self._list.viewport_start + vp, n)
                text = f"-- rows {lo}-{hi} of {n} --"
            else:
                text = f"-- {n} row(s) --"
            self._state.status_text.set(text)

        def quit(
            self, exit_code: int = 0, result_message: Optional[str] = None
        ) -> None:
            raise ExitEventLoop(
                "quit", exit_code=exit_code, result_message=result_message
            )

        def toggle_help(self) -> None:
            self._help_popup.toggle()

    exit_code, result = _RepoCdPickerApp().run_with_result()

    # After Session exits, execute shell command if a repo was selected.
    # This ensures terminal is properly restored (alt screen, cursor, termios)
    # before spawning the interactive shell.
    if exit_code == 0 and result is not None:
        shell_cd = "$SHELL -c 'cd {0} && exec $SHELL'"
        executor.exec(shell_cd.format(result), flags=WAITING)
    return exit_code, None
