"""
Module: pigit/app_rebase.py
Description: Interactive rebase todo-list panel (edit actions and order, then execute).
Author: Zev
Date: 2026-08-14
"""

from __future__ import annotations

import os
import shlex
import tempfile
from dataclasses import dataclass
from typing import TYPE_CHECKING
from collections.abc import Callable

from pigit.termui import (
    Segment,
    FeedbackKind,
    bind_action,
    exec_external,
    palette,
    request_render,
    show_badge,
    show_toast,
)
from pigit.termui.widgets import AlertDialog, OptionList

from .app_theme import THEME
from .git.api import GitError

if TYPE_CHECKING:
    from pigit.git.api import GitApi

# Ordered git sequence commands; squash/fixup merge into the previous line.
_ACTION_FG = {
    "pick": THEME.fg_primary,
    "squash": THEME.fg_info,
    "fixup": THEME.fg_info,
    "drop": THEME.fg_danger,
    "reword": THEME.fg_warning,
    "edit": THEME.fg_warning,
}
# Actions that merge into the previous commit and therefore cannot be first.
_MERGE_ACTIONS = ("squash", "fixup")


@dataclass
class _TodoItem:
    """One editable line of the rebase todo list."""

    sha: str
    subject: str
    action: str = "pick"


class RebasePanel(OptionList):
    """Sheet overlay for editing the interactive-rebase todo list."""

    CURSOR = "●"
    keymap_namespace = "rebase"

    def __init__(
        self,
        git: "GitApi",
        base: str,
        on_done: Callable[[], None],
        get_record_rewind: Callable[[], Callable[[str, str], None]],
    ) -> None:
        super().__init__()
        self._git = git
        self._base = base
        self._on_done = on_done
        self._get_record_rewind = get_record_rewind
        self._items: list[_TodoItem] = []
        self._alert = AlertDialog(inner_width=50, on_result=lambda _: None)

    def preferred_sheet_height(self, term_h: int) -> int:
        """Room for the todo list; host should use max_fraction=0.5."""
        return min(20, max(3, term_h - 4))

    def mount(self) -> None:
        """Load the range and validate; dismiss on any guard failure."""
        from .app_bisect import guard_bisect_active, guard_sequencer_active

        super().mount()
        if guard_sequencer_active(self._git):
            self._on_done()
            return
        if guard_bisect_active(self._git):
            self._on_done()
            return
        try:
            commits = self._git.list_commits_in_range(self._base)
        except GitError as e:
            show_toast(
                f"Rebase range error: {e}", duration=2.0, kind=FeedbackKind.ERROR
            )
            self._on_done()
            return
        if not commits:
            show_toast("No commits to rebase", duration=2.0, kind=FeedbackKind.WARNING)
            self._on_done()
            return
        if any(c.is_merge for c in commits):
            show_toast(
                "Range contains merges (unsupported)",
                duration=2.0,
                kind=FeedbackKind.WARNING,
            )
            self._on_done()
            return
        self._items = [_TodoItem(c.sha, c.msg) for c in commits]
        self.set_content([self._display(item) for item in self._items])

    def _display(self, item: _TodoItem) -> str:
        """Return the plain-text form of an item (used as OptionList content)."""
        return f"{item.action} {item.sha[:8]} {item.subject}"

    @bind_action("next", "j", "down", desc="Navigate todo list", tip="Navigate")
    def next(self, step: int = 1) -> None:
        super().next(step)

    @bind_action("previous", "k", "up", desc="Navigate todo list", tip="Navigate")
    def previous(self, step: int = 1) -> None:
        super().previous(step)

    @bind_action(
        "confirm", "enter", desc="Confirm and execute the rebase", tip="Confirm"
    )
    def confirm(self) -> None:
        self._confirm()

    @bind_action("cancel", "esc", desc="Cancel the rebase", tip="Cancel")
    def cancel(self) -> None:
        self._on_done()

    @bind_action("move_up", "J", desc="Move commit up", tip="Move up")
    def move_up(self) -> None:
        self._move_up()

    @bind_action("move_down", "K", desc="Move commit down", tip="Move down")
    def move_down(self) -> None:
        self._move_down()

    @bind_action("pick", "p", desc="Keep this commit", tip="pick")
    def action_pick(self) -> None:
        self._set_action("pick")

    @bind_action(
        "squash",
        "s",
        desc="Squash into previous commit (combines messages)",
        tip="squash",
    )
    def action_squash(self) -> None:
        self._set_action("squash")

    @bind_action(
        "fixup",
        "f",
        desc="Fixup into previous commit (discards its message)",
        tip="fixup",
    )
    def action_fixup(self) -> None:
        self._set_action("fixup")

    @bind_action(
        "reword", "r", desc="Reword commit message (opens $EDITOR)", tip="reword"
    )
    def action_reword(self) -> None:
        self._set_action("reword")

    @bind_action(
        "edit", "e", desc="Edit this commit (stops for manual changes)", tip="edit"
    )
    def action_edit(self) -> None:
        self._set_action("edit")

    @bind_action("drop", "d", desc="Drop this commit (irreversible)", tip="drop")
    def action_drop(self) -> None:
        self._set_action("drop")

    def describe_row(
        self,
        idx: int,
        is_cursor: bool,
        *,
        item_idx: int | None = None,
        sub_row: int = 0,
    ) -> tuple[list[Segment], list[Segment] | None, list[Segment]]:
        """Render one todo row: cursor, colored action, short sha + subject."""
        item = self._items[idx]
        flags = palette.STYLE_BOLD if is_cursor else 0
        left = [
            Segment(" ", fg=THEME.fg_primary),
            Segment(
                item.action.ljust(7),
                fg=_ACTION_FG[item.action],
                style_flags=flags,
            ),
        ]
        subject_fg = THEME.fg_primary if is_cursor else THEME.fg_muted
        main = [
            Segment(f"{item.sha[:8]}  ", fg=THEME.fg_muted, style_flags=flags),
            Segment(item.subject, fg=subject_fg, style_flags=flags),
        ]
        return left, main, []

    # ── editing ──

    def _set_action(self, action: str) -> None:
        """Set the current row's action, rejecting squash/fixup on the first row."""
        idx = self.curr_no
        if action in _MERGE_ACTIONS and idx == 0:
            show_toast(
                "Cannot squash/fixup the first commit",
                duration=1.5,
                kind=FeedbackKind.WARNING,
            )
            return
        self._items[idx].action = action
        request_render()

    def _move_up(self) -> None:
        """Move the current row up, rejecting moves that put squash/fixup first."""
        idx = self.curr_no
        if idx == 0:
            return
        if idx == 1 and self._items[idx].action in _MERGE_ACTIONS:
            show_toast(
                "Cannot move squash/fixup to the top",
                duration=1.5,
                kind=FeedbackKind.WARNING,
            )
            return
        self._items[idx], self._items[idx - 1] = self._items[idx - 1], self._items[idx]
        self.curr_no = idx - 1

    def _move_down(self) -> None:
        """Move the current row down, rejecting moves that put squash/fixup first."""
        idx = self.curr_no
        if idx >= len(self._items) - 1:
            return
        if idx == 0 and self._items[idx + 1].action in _MERGE_ACTIONS:
            show_toast(
                "Cannot move squash/fixup to the top",
                duration=1.5,
                kind=FeedbackKind.WARNING,
            )
            return
        self._items[idx], self._items[idx + 1] = self._items[idx + 1], self._items[idx]
        self.curr_no = idx + 1

    # ── execute ──

    def _confirm(self) -> None:
        """Validate the todo and ask for confirmation before executing."""
        error = self._validate()
        if error is not None:
            show_toast(error, duration=2.0, kind=FeedbackKind.WARNING)
            return
        n = len(self._items)
        self._alert.alert(
            f"Rewrite {n} commits? This rewrites history.",
            self._on_confirm_result,
            kind=FeedbackKind.ERROR,
        )

    def _validate(self) -> str | None:
        """Return an error message if the todo is invalid, otherwise None.

        squash/fixup merge into the previous commit, so they cannot be first
        nor follow a dropped commit.
        """
        prev_action: str | None = None
        for item in self._items:
            if item.action in _MERGE_ACTIONS:
                if prev_action is None or prev_action == "drop":
                    return "squash/fixup needs a non-dropped commit above it"
            prev_action = item.action
        return None

    def _on_confirm_result(self, confirmed: bool) -> None:
        """Execute the rebase when the user confirms."""
        if confirmed:
            self._execute()

    def _execute(self) -> None:
        """Write the todo and run the rebase; always dismiss on completion."""
        todo_lines = [
            f"{item.action} {item.sha} {item.subject}" for item in self._items
        ]
        tmp = tempfile.NamedTemporaryFile("w", suffix=".todo", delete=False)
        tmp.write("\n".join(todo_lines))
        tmp.close()
        try:
            pre_sha = self._git.resolve_head_sha()
            result = exec_external(
                ["git", "rebase", "-i", self._base],
                cwd=self._git.path,
                env={
                    **os.environ,
                    "GIT_SEQUENCE_EDITOR": f"cp {shlex.quote(tmp.name)}",
                },
            )
            if self._git.is_rebase_in_progress():
                show_toast(
                    "Rebase paused. Resolve/edit, then ';' → rebase-continue/abort/skip",
                    duration=3.0,
                    kind=FeedbackKind.WARNING,
                )
            elif result.returncode != 0:
                show_toast("Rebase failed", duration=2.0, kind=FeedbackKind.ERROR)
            else:
                show_badge("Rebase complete", duration=1.5, kind=FeedbackKind.SUCCESS)
                # A completed rebase moved HEAD; record a rewind point so ``u``
                # can return to the pre-rebase commit.
                self._get_record_rewind()(f"Rebase onto {self._base}", pre_sha)
        except Exception as e:
            show_toast(f"Rebase error: {e}", duration=3.0, kind=FeedbackKind.ERROR)
        finally:
            os.unlink(tmp.name)
            self._on_done()
