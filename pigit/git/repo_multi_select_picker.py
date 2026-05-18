"""
Module: pigit/git/repo_multi_select_picker.py
Description: Multi-select TTY picker for repo operations.
Author: Zev
Date: 2026-05-15
"""

from __future__ import annotations

from collections.abc import Sequence

from pigit.termui import ExitEventLoop, palette
from pigit.picker_app import BasePickerApp, PickerRow
from pigit.termui._segment import Segment
from pigit.termui.widgets import CheckList
from pigit.termui.tty_io import tty_ok

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


def _render_status_symbol(
    ch: str, bg: tuple[int, int, int] | None, row_style: int
) -> Segment:
    """Map a status character to a colored Segment."""
    fg = (
        _RED
        if ch == "*"
        else _GREEN if ch == "+" else _YELLOW if ch == "?" else _FG_PRIMARY
    )
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
        source_idx = self.visible_to_source(idx)
        row = app._rows[source_idx]
        status = app._repo_status.get(row.title)
        path = row.ref if isinstance(row.ref, str) else ""
        is_checked = idx in self._checked
        if is_checked:
            bg = palette.BG_ACTIVE
        elif is_cursor:
            bg = palette.BG_HOVER
        else:
            bg = None
        row_style = _BOLD if is_cursor else 0

        marker = (
            Segment(self.CHECKED, fg=_GREEN, bg=bg, style_flags=row_style)
            if is_checked
            else Segment(self.UNCHECKED, fg=_FG_MUTED, bg=bg, style_flags=row_style)
        )

        name_seg = Segment(row.title, fg=_FG_PRIMARY, bg=bg, style_flags=row_style)

        main: list[Segment] = [
            name_seg,
            Segment("  ", fg=_FG_PRIMARY, bg=bg, style_flags=row_style),
        ]

        if status is not None:
            branch_seg = Segment(status.branch, fg=_BLUE, bg=bg, style_flags=row_style)
            main.append(branch_seg)
            if status.symbols:
                main.append(Segment(" ", fg=_FG_PRIMARY, bg=bg, style_flags=row_style))
                main.extend(
                    _render_status_symbol(ch, bg, row_style) for ch in status.symbols
                )

        right = [Segment(path, fg=_FG_MUTED, bg=bg, style_flags=row_style)]
        return (
            [marker, Segment(" ", fg=_FG_PRIMARY, bg=bg, style_flags=row_style)],
            main,
            right,
        )


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

    class _MultiSelectPickerApp(BasePickerApp):
        _list: CheckList

        def __init__(self) -> None:
            super().__init__(initial_filter=initial_filter)
            self._rows = rows
            self._repo_status = query_repos_status(rows)

        def get_title(self) -> str:
            return header_title

        def build_list(self) -> CheckList:
            lst = _MkbranchCheckList(
                self,
                on_selection_changed=lambda _: self._update_status(),
            )
            lst.set_source_content([r.title for r in self._rows])
            return lst

        def on_key_extra(self, key: str) -> None:
            if key == " ":
                self._list.toggle()
                self._update_status()
            elif key == "a":
                self._list.select_all()
                self._update_status()
            elif key == "n":
                self._list.select_none()
                self._update_status()

        def on_confirm(self) -> None:
            selected = self._list.get_selected()
            if not selected:
                raise ExitEventLoop("quit", exit_code=0, result_message=[])
            names = [
                self._rows[self._list.visible_to_source(i)].title
                for i in sorted(selected)
            ]
            raise ExitEventLoop("done", exit_code=0, result_message=names)

        def get_terminal_too_small_msg(self) -> str:
            return _MS_TERMINAL_TOO_SMALL_MSG

        def _update_status(self) -> None:
            n_selected = len(self._list.get_selected())
            n_total = len(self._list.content)
            self._status.set_text(f"{n_selected} selected / {n_total} total")

    exit_code, result = _MultiSelectPickerApp().run_with_result()

    if exit_code == 0 and isinstance(result, list):
        return 0, result
    return exit_code, []
