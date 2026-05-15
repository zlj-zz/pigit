"""
Module: pigit/git/repo_cd_picker.py
Description: TTY picker for ``pigit repo cd --pick``.
Author: Zev
Date: 2026-04-20
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from collections.abc import Sequence

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
    palette,
)
from pigit.termui._component_widgets import BG_HOVER
from pigit.termui._picker import (
    PICK_EXIT_CTRL_C,
    PickerHeader,
    PickerMode,
    PickerRow,
    PickerState,
    apply_picker_filter,
    picker_terminal_ok,
)
from pigit.termui._segment import Segment
from pigit.termui.tty_io import terminal_size, tty_ok

from ._repo_status import query_repos_status

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


class _RepoCdItemSelector(ItemSelector):
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
        bg = BG_HOVER if is_cursor else None
        row_style = _BOLD if is_cursor else 0

        left = [Segment("  ", fg=_FG_PRIMARY, bg=bg, style_flags=row_style)]
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
        return (left, main, right)


def run_repo_cd_picker(
    rows: Sequence[PickerRow],
    executor: Executor,
    *,
    initial_filter: str = "",
    pick_alt_screen: bool = False,
) -> tuple[int, str | None]:
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
            self._repo_status = query_repos_status(rows)

        def build_root(self) -> Component:
            self._header = PickerHeader(title)
            self._list = _RepoCdItemSelector(
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
                "j/k scroll, Enter cd, / filter, ? help",
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
            filtered = apply_picker_filter(self._rows, needle)
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
            text = f"{n} repos"
            self._state.status_text.set(text)

        def quit(self, exit_code: int = 0, result_message: str | None = None) -> None:
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
