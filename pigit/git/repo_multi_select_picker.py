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
    StatusBar,
    Popup,
    keys,
    palette,
)
from pigit.termui._component_widgets import BG_ACTIVE, BG_HOVER, CheckList
from pigit.termui._picker import (
    PICK_EXIT_CTRL_C,
    PickerHeader,
    PickerMode,
    PickerRow,
    PickerState,
    apply_picker_filter_regex,
    picker_terminal_ok,
)
from pigit.termui._segment import Segment
from pigit.termui.tty_io import terminal_size, tty_ok

from ._repo_status import query_repos_status

_MS_TERMINAL_TOO_SMALL_MSG = (
    "Terminal is too small for the interactive picker (need room for a fixed header, "
    "at least one list row, and a footer line). Enlarge the window or use "
    "explicit repo names."
)

EMPTY_MANAGED_REPOS_MSG = "No managed repos; use `pigit repo add`."

_BLUE = palette.BLUE
_RED = palette.RED
_GREEN = palette.GREEN
_YELLOW = palette.YELLOW
_FG_PRIMARY = palette.DEFAULT_FG
_FG_MUTED = palette.DEFAULT_FG_DIM
_BOLD = palette.STYLE_BOLD


def _render_status_symbol(ch: str, bg: tuple[int, int, int] | None, row_style: int) -> Segment:
    """Map a status character to a colored Segment."""
    fg = _RED if ch == "*" else _GREEN if ch == "+" else _YELLOW if ch == "?" else _FG_PRIMARY
    return Segment(ch, fg=fg, bg=bg, style_flags=row_style)


class _MkbranchCheckList(CheckList):
    def __init__(self, app, **kwargs) -> None:
        super().__init__(**kwargs)
        self._app = app

    def describe_row(
        self,
        idx: int,
        is_cursor: bool,
        *,
        item_idx: int | None = None,
        sub_row: int = 0,
    ) -> tuple[list[Segment], list[Segment] | None, list[Segment]]:
        app = self._app
        row = app._filtered_rows[idx]
        status = app._repo_status.get(row.title)
        path = row.ref if isinstance(row.ref, str) else ""
        is_checked = idx in self._checked
        if is_checked:
            bg = BG_ACTIVE
        elif is_cursor:
            bg = BG_HOVER
        else:
            bg = None
        row_style = _BOLD if is_cursor else 0

        marker = (
            Segment(self.CHECKED, fg=_GREEN, bg=bg, style_flags=row_style)
            if is_checked
            else Segment(self.UNCHECKED, fg=_FG_MUTED, bg=bg, style_flags=row_style)
        )

        name_seg = Segment(row.title, fg=_FG_PRIMARY, bg=bg, style_flags=row_style)

        main: list[Segment] = [name_seg, Segment("  ", fg=_FG_PRIMARY, bg=bg, style_flags=row_style)]

        if status is not None:
            branch_seg = Segment(status.branch, fg=_BLUE, bg=bg, style_flags=row_style)
            main.append(branch_seg)
            if status.symbols:
                main.append(Segment(" ", fg=_FG_PRIMARY, bg=bg, style_flags=row_style))
                main.extend(
                    _render_status_symbol(ch, bg, row_style) for ch in status.symbols
                )

        right = [Segment(path, fg=_FG_MUTED, bg=bg, style_flags=row_style)]
        return ([marker, Segment(" ", fg=_FG_PRIMARY, bg=bg, style_flags=row_style)], main, right)


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
            self._repo_status = query_repos_status(rows)

        def build_root(self) -> Component:
            self._header = PickerHeader(header_title)
            self._list = _MkbranchCheckList(
                self,
                content=[r.title for r in self._filtered_rows],
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
                heights=[2, "flex", 1, 0],
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
                raise ExitEventLoop(
                    "quit", exit_code=1, result_message=_MS_TERMINAL_TOO_SMALL_MSG
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
                raise ExitEventLoop("quit", exit_code=0, result_message=None)
            elif key == "?":
                self._help_popup.toggle()

        # --- Filter mode ---

        def _on_filter_value_changed(self, text: str) -> None:
            self._state.filter_text.set(text)
            self._apply_filter()

        def _enter_filter(self) -> None:
            self._mode = PickerMode.FILTER
            self._input.set_visible(True)
            self._layout.set_heights([2, "flex", 1, 1])
            self.resize(self._loop.get_term_size())

        def _exit_filter(self) -> None:
            self._mode = PickerMode.BROWSE
            self._input.set_visible(False)
            self._layout.set_heights([2, "flex", 1, 0])
            self.resize(self._loop.get_term_size())

        def _apply_filter(self) -> None:
            needle = self._input.value
            if needle == self._last_needle:
                return
            self._last_needle = needle
            filtered = apply_picker_filter_regex(self._rows, needle)
            self._filtered_rows = filtered
            self._list.set_content([r.title for r in filtered])
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
                raise ExitEventLoop("quit", exit_code=0, result_message=[])
            names = [self._filtered_rows[i].title for i in sorted(selected)]
            raise ExitEventLoop("done", exit_code=0, result_message=names)

        def _update_status(self, _idx: int) -> None:
            n_selected = len(self._list.get_selected())
            n_total = len(self._list.content)
            text = f"{n_selected} selected / {n_total} total"
            self._state.status_text.set(text)

        def quit(self, exit_code: int = 0, result_message: str | None = None) -> None:
            raise ExitEventLoop(
                "quit", exit_code=exit_code, result_message=result_message
            )

        def toggle_help(self) -> None:
            self._help_popup.toggle()

    exit_code, result = _MultiSelectPickerApp().run_with_result()

    if exit_code == 0 and isinstance(result, list):
        return 0, result
    return exit_code, []
