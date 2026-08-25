"""
Module: pigit/app_commit_editor.py
Description: Inline commit message editor (Sheet overlay).
Author: Zev
Date: 2026-05-29
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from collections.abc import Callable

from pigit.termui import FeedbackKind, keys, show_toast, Component
from pigit.termui.containers import Column, Row
from pigit.termui.widgets import InputLine, Label, LintBar, ShortcutHints, StaticList
from pigit.termui.types import OverlayDispatchResult
from .app_theme import THEME

if TYPE_CHECKING:
    from pigit.git.model import File
    from pigit.viewmodels.status import IStatusViewModel
    from pigit.termui import Surface


_HANDLED = OverlayDispatchResult.HANDLED_EXPLICIT

_SHORTCUT_PAIRS: tuple[tuple[str, str], ...] = (
    ("Tab", "body"),
    ("Ctrl+Enter", "commit"),
    ("Esc", "cancel"),
)


def _staged_row_style(_index: int, row: str) -> tuple[int, int, int] | None:
    """Map staged status letter in ``"  X name"`` rows to theme colors."""
    staged = row[2] if len(row) > 2 else " "
    if staged in "MA":
        return THEME.fg_success
    if staged == "D":
        return THEME.fg_danger
    if staged in "RC":
        return THEME.fg_warning
    return THEME.fg_dim


def _staged_rows(files: list[File]) -> list[str]:
    rows: list[str] = []
    for f in files:
        staged = f.short_status[0] if len(f.short_status) > 0 else " "
        rows.append(f"  {staged} {f.name}")
    return rows


class CommitEditor(Component):
    """Inline commit message editor embedded in a Sheet overlay."""

    def __init__(
        self,
        *,
        vm: IStatusViewModel,
        staged_files: list[File],
        on_submit: Callable[[str], None],
        on_cancel: Callable[[], None],
    ) -> None:
        super().__init__()
        self._vm = vm
        self._staged_files = staged_files
        self._on_submit = on_submit
        self._on_cancel = on_cancel

        self._subject = InputLine(
            allow_newline=False,
            placeholder="Summary of the change",
            on_submit=self._focus_body,
        )
        self._body = InputLine(
            allow_newline=True,
            placeholder="Detailed description of the change (optional)",
        )
        self._lint_bar = LintBar(self._subject, self._body)
        self._shortcut_hints = ShortcutHints(_SHORTCUT_PAIRS, bg=THEME.bg_base)
        self._status_bar = Row(
            children=[self._lint_bar, self._shortcut_hints],
            widths=["flex", self._shortcut_hints.preferred_width],
        )
        self._focus_index = 0

        self._staged_header = Label(
            f"Staged ({len(staged_files)})",
            fg=THEME.fg_dim,
            bg=THEME.bg_chrome,
        )
        self._staged_list = StaticList(
            _staged_rows(staged_files),
            empty_text="  No staged files",
            row_style=_staged_row_style,
            fg=THEME.fg_dim,
            bg=THEME.bg_chrome,
        )

        self._editor_col = Column(
            children=[self._subject, self._body, self._status_bar],
            heights=[1, "flex", 1],
        )
        self._staged_col = Column(
            children=[self._staged_header, self._staged_list],
            heights=[1, "flex"],
        )
        self._root = Row(
            children=[self._editor_col, self._staged_col],
            widths=["flex", "flex"],
        )

    def preferred_sheet_height(self, term_h: int) -> int:
        """About 35% of the terminal; host should use max_fraction=0.5."""
        return min(term_h - 2, max(10, int(term_h * 0.35)))

    @property
    def focus_child(self) -> Component | None:
        """Return the currently focused input."""
        return self._current_input()

    def paint(self, surface: Surface) -> None:
        self._root.paint(surface)

    def resize(self, size: tuple[int, int]) -> None:
        self._size = size
        self._root.resize(size)

    def mount(self) -> None:
        super().mount()
        self._subject.set_value("")
        self._body.set_value("")
        self._status_bar.mount()
        self._staged_header.mount()
        self._staged_list.mount()

    def unmount(self) -> None:
        super().unmount()
        self._status_bar.unmount()
        self._staged_header.unmount()
        self._staged_list.unmount()

    def _current_input(self) -> InputLine:
        return self._subject if self._focus_index == 0 else self._body

    def dispatch_overlay_key(self, key: str) -> OverlayDispatchResult:
        if key == keys.KEY_ESC:
            self._on_cancel()
            return _HANDLED
        if key == keys.KEY_CTRL_ENTER:
            self._submit()
            return _HANDLED
        if key == keys.KEY_TAB:
            self._focus_index = 1
            return _HANDLED
        if key == keys.KEY_SHIFT_TAB:
            self._focus_index = 0
            return _HANDLED
        return self._current_input().dispatch_overlay_key(key)

    def _focus_body(self, _: str) -> None:
        self._focus_index = 1

    def _submit(self) -> None:
        subject = self._subject.value.strip()
        body = self._body.value.strip()
        if not subject:
            show_toast("Subject is required", duration=1.5, kind=FeedbackKind.WARNING)
            return
        message = subject + ("\n\n" + body if body else "")
        lint = self._lint_check(subject, body)
        if lint:
            show_toast(lint, duration=1.5, kind=FeedbackKind.WARNING)
            return
        self._on_submit(message)

    def _lint_check(self, subject: str, body: str) -> str | None:
        if len(subject) > 50:
            return f"Subject too long: {len(subject)}/50"
        if subject.endswith("."):
            return "Subject should not end with a period"
        for i, line in enumerate(body.split("\n"), start=1):
            if len(line) > 72:
                return f"Body line {i} too long: {len(line)}/72"
        return None
