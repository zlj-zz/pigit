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

from pigit.termui import ExitEventLoop, palette
from pigit.picker_app import BasePickerApp, PickerRow
from pigit.termui._segment import Segment
from pigit.termui.widgets import ItemList
from pigit.termui.tty_io import tty_ok

from ._repo_status import query_repos_status

if TYPE_CHECKING:
    from pigit.ext.executor import Executor

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
        status = app._repo_status.get(row.title)
        path = row.ref if isinstance(row.ref, str) else ""
        bg = palette.BG_HOVER if is_cursor else None
        row_style = _BOLD if is_cursor else 0

        left = [Segment("  ", fg=_FG_PRIMARY, bg=bg, style_flags=row_style)]
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
        return (left, main, right)


def run_repo_cd_picker(
    rows: Sequence[PickerRow],
    executor: Executor,
    *,
    initial_filter: str = "",
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

    if exit_code == 0 and result is not None:
        shell_cd = "$SHELL -c 'cd {0} && exec $SHELL'"
        executor.exec(shell_cd.format(result), flags=WAITING)
    return exit_code, None
