"""
Module: pigit/handlers/repo_picker.py
Description: TUI pickers for repo operations (cd, multi-select).
Author: Zev
Date: 2026-05-23
"""

from __future__ import annotations

from collections.abc import Sequence

from pigit.termui import ExitEventLoop, palette
from pigit.picker_app import BasePickerApp, PickerRow
from pigit.termui._segment import Segment
from pigit.termui.widgets import CheckList, ItemList
from pigit.termui.tty_io import tty_ok

from pigit.git._repo_status import query_repos_status

EMPTY_MANAGED_REPOS_MSG = "No managed repos; use `pigit repo add`."

REPO_CD_NO_TTY_MSG = (
    "@red(pigit repo cd --pick) needs an interactive terminal.\n"
    "Use an explicit managed repo name in scripts and CI, or run "
    "`pigit repo cd --pick` only in a real terminal.\n"
    "See `pigit repo cd -h`."
)

_REPO_CD_TERMINAL_TOO_SMALL_MSG = (
    "Terminal is too small for `pigit repo cd --pick` (need room for a fixed header, "
    "at least one list row, and a footer line). Enlarge the window or use a "
    "non-interactive repo name."
)

_MS_TERMINAL_TOO_SMALL_MSG = (
    "Terminal is too small for the interactive picker (need room for a fixed header, "
    "at least one list row, and a footer line). Enlarge the window or use "
    "explicit repo names."
)


def _render_status_symbol(
    ch: str, bg: tuple[int, int, int] | None, row_style: int
) -> Segment:
    """Map a status character to a colored Segment."""
    fg = (
        palette.RED
        if ch == "*"
        else (
            palette.GREEN
            if ch == "+"
            else palette.YELLOW if ch == "?" else palette.DEFAULT_FG
        )
    )
    return Segment(ch, fg=fg, bg=bg, style_flags=row_style)


def _build_repo_row_body(
    row: PickerRow,
    status,
    bg: tuple[int, int, int] | None,
    row_style: int,
) -> tuple[list[Segment], list[Segment]]:
    """Build the main and right segments for a repo row."""
    main: list[Segment] = [
        Segment(row.title, fg=palette.DEFAULT_FG, bg=bg, style_flags=row_style),
        Segment("  ", fg=palette.DEFAULT_FG, bg=bg, style_flags=row_style),
    ]

    if status is not None:
        branch_seg = Segment(
            status.branch, fg=palette.BLUE, bg=bg, style_flags=row_style
        )
        main.append(branch_seg)
        if status.symbols:
            main.append(
                Segment(" ", fg=palette.DEFAULT_FG, bg=bg, style_flags=row_style)
            )
            main.extend(
                _render_status_symbol(ch, bg, row_style) for ch in status.symbols
            )

    right = [
        Segment(
            row.ref if isinstance(row.ref, str) else "",
            fg=palette.DEFAULT_FG_DIM,
            bg=bg,
            style_flags=row_style,
        )
    ]
    return main, right


# ---------------------------------------------------------------------------
# Repo CD picker
# ---------------------------------------------------------------------------


class _RepoCdItemList(ItemList):
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
        bg = palette.BG_HOVER if is_cursor else None
        row_style = palette.STYLE_BOLD if is_cursor else 0

        left = [Segment("  ", fg=palette.DEFAULT_FG, bg=bg, style_flags=row_style)]
        main, right = _build_repo_row_body(
            row, app._repo_status.get(row.title), bg, row_style
        )
        return (left, main, right)


def run_repo_cd_picker(
    rows: Sequence[PickerRow],
    *,
    initial_filter: str = "",
) -> tuple[int, str | None]:
    """Interactive repo directory picker; on confirm returns the selected path.

    Requires a real TTY (same gate as :func:`tty_ok`).

    Returns:
        ``(exit_code, path | None)``. ``0`` with the selected path, or ``None`` on quit.
    """
    if not rows:
        return 1, EMPTY_MANAGED_REPOS_MSG
    if not tty_ok():
        return 1, REPO_CD_NO_TTY_MSG

    title = (
        "pigit repo cd --pick  "
        "[j/k scroll  Enter cd  / filter  q/Esc quit  Ctrl+C abort]"
    )

    class _RepoCdPickerApp(BasePickerApp):
        def __init__(self) -> None:
            super().__init__(initial_filter=initial_filter)
            self._rows = rows
            self._repo_status = query_repos_status(rows)

        def get_title(self) -> str:
            return title

        def build_list(self) -> ItemList:
            lst = _RepoCdItemList(
                self,
                on_selection_changed=lambda _: self._update_status(),
            )
            lst.set_source_content([r.title for r in self._rows])
            return lst

        def on_confirm(self) -> None:
            idx = self._list.source_index
            if idx < 0 or idx >= len(self._rows):
                return
            path = self._rows[idx].ref
            assert isinstance(path, str)
            raise ExitEventLoop("done", exit_code=0, result_message=path)

        def get_terminal_too_small_msg(self) -> str:
            return _REPO_CD_TERMINAL_TOO_SMALL_MSG

        def _update_status(self) -> None:
            n = len(self._list.content)
            self._status.set_text(f"{n} repos")

    exit_code, result = _RepoCdPickerApp().run_with_result()
    return exit_code, result


# ---------------------------------------------------------------------------
# Multi-select picker
# ---------------------------------------------------------------------------


class _RepoCheckList(CheckList):
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
        is_checked = idx in self._checked
        if is_checked:
            bg = palette.BG_ACTIVE
        elif is_cursor:
            bg = palette.BG_HOVER
        else:
            bg = None
        row_style = palette.STYLE_BOLD if is_cursor else 0

        marker = (
            Segment(self.CHECKED, fg=palette.GREEN, bg=bg, style_flags=row_style)
            if is_checked
            else Segment(
                self.UNCHECKED, fg=palette.DEFAULT_FG_DIM, bg=bg, style_flags=row_style
            )
        )

        main, right = _build_repo_row_body(
            row, app._repo_status.get(row.title), bg, row_style
        )
        left = [
            marker,
            Segment(" ", fg=palette.DEFAULT_FG, bg=bg, style_flags=row_style),
        ]
        return (left, main, right)


def run_multi_select_picker(
    rows: Sequence[PickerRow],
    title: str,
    *,
    initial_filter: str = "",
) -> tuple[int, list[str]]:
    """Interactive multi-select picker.

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
            lst = _RepoCheckList(
                self,
                on_selection_changed=lambda _: self._update_status(),
            )
            lst.set_source_content([r.title for r in self._rows])
            return lst

        def _extra_help_entries(self) -> list[tuple[str, str]]:
            return [
                ("Space", "Toggle selection"),
                ("a", "Select all"),
                ("n", "Select none"),
            ]

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
