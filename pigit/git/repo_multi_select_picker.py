"""
Module: pigit/git/repo_multi_select_picker.py
Description: Multi-select TTY picker for repo operations.
Author: Zev
Date: 2026-05-15
"""

from __future__ import annotations

from collections.abc import Sequence

from pigit.termui import (
    Application,
    Column,
    Component,
    ComponentRoot,
    ExitEventLoop,
    HelpPanel,
    InputLine,
    Popup,
    StatusBar,
    keys,
)
from pigit.termui._component_widgets import CheckList
from pigit.termui._picker import (
    PICK_EXIT_CTRL_C,
    PickerHeader,
    PickerMode,
    PickerRow,
    PickerState,
    apply_picker_filter_regex,
    picker_terminal_ok,
)
from pigit.termui.tty_io import terminal_size, tty_ok

_MS_TERMINAL_TOO_SMALL_MSG = (
    "Terminal is too small for the interactive picker (need room for a fixed header, "
    "at least one list row, and a footer line). Enlarge the window or use "
    "explicit repo names."
)

EMPTY_MANAGED_REPOS_MSG = "No managed repos; use `pigit repo add`."


def run_multi_select_picker(
    rows: Sequence[PickerRow],
    title: str,
    *,
    initial_filter: str = "",
) -> tuple[int, list[str]]:
    """
    Interactive multi-select picker.

    Returns:
        ``(exit_code, selected_repo_names)``. ``0`` on confirm, ``130`` on Ctrl+C.
        Empty list if user cancelled or selected nothing.
    """
    if not rows:
        return 1, []
    if not tty_ok():
        return 1, []

    header_title = (
        f"{title}  "
        "[j/k ↑↓  Space toggle  a all  n none  / filter  Enter confirm  q quit]"
    )

    rendered = [f"{r.title}  {r.detail}" for r in rows]

    class _MultiSelectPickerApp(Application):
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
            self._header = PickerHeader(header_title)
            self._list = CheckList(
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
                "j/k move, Space toggle, a all, n none, Enter confirm, ? help",
                duration=3.0,
            )
            self._help_panel = HelpPanel()
            self._help_popup = Popup(
                self._help_panel,
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
                    result_message=_MS_TERMINAL_TOO_SMALL_MSG,
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
            elif key == " ":
                self._list.toggle()
                self._update_status(self._list.curr_no)
            elif key == "a":
                self._list.select_all()
                self._update_status(self._list.curr_no)
            elif key == "n":
                self._list.select_none()
                self._update_status(self._list.curr_no)
            elif key == "enter":
                self._confirm_selection()
            elif key == "/":
                self._enter_filter()
            elif key in ("q", keys.KEY_ESC):
                self.quit()
            elif key == "?":
                self._help_popup.toggle()

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
            filtered = apply_picker_filter_regex(self._rows, needle)
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

        def _confirm_selection(self) -> None:
            selected = self._list.get_selected()
            if not selected:
                self.quit(exit_code=0, result_message=[])
                return
            names = [self._filtered_rows[i].title for i in sorted(selected)]
            raise ExitEventLoop("done", exit_code=0, result_message=names)

        def _update_status(self, _idx: int) -> None:
            n_selected = len(self._list.get_selected())
            n_total = len(self._list.content)
            vp = self._list.visible_row_count
            if n_total > vp:
                lo = self._list.viewport_start + 1
                hi = min(self._list.viewport_start + vp, n_total)
                text = f"-- {n_selected} selected / {n_total} total  rows {lo}-{hi} --"
            else:
                text = f"-- {n_selected} selected / {n_total} total --"
            self._state.status_text.set(text)

        def quit(self, exit_code: int = 0, result_message: list[str] | None = None) -> None:
            raise ExitEventLoop(
                "quit", exit_code=exit_code, result_message=result_message
            )

        def toggle_help(self) -> None:
            self._help_popup.toggle()

    exit_code, result = _MultiSelectPickerApp().run_with_result()

    if exit_code == 0 and isinstance(result, list):
        return 0, result
    return exit_code, []
