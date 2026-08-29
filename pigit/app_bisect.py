"""
Module: pigit/app_bisect.py
Description: Bisect status sheet and the shared bisect-active gate.
Author: Zev
Date: 2026-08-28
"""

from __future__ import annotations

import math
from collections.abc import Callable
from typing import TYPE_CHECKING

from pigit.ext.utils import split_at_most
from pigit.git.api import GitError
from pigit.termui import (
    FeedbackKind,
    bind_action,
    dismiss_sheet,
    show_toast,
)
from pigit.termui.widgets import OptionList

if TYPE_CHECKING:
    from pigit.git.api import BisectState, GitApi


def guard_bisect_active(git: GitApi) -> bool:
    """Return True when a bisect is active; toast and block the caller."""
    if git.bisect_status() is not None:
        show_toast(
            "A bisect is in progress",
            duration=2.0,
            kind=FeedbackKind.WARNING,
        )
        return True
    return False


def guard_sequencer_active(git: GitApi) -> bool:
    """Return True when a merge/rebase/cherry-pick is running; block the caller."""
    kind = git.sequencer_in_progress()
    if kind is not None:
        show_toast(
            f"A {kind} is already in progress",
            duration=2.0,
            kind=FeedbackKind.WARNING,
        )
        return True
    return False


def parse_bisect_start_input(raw: str) -> tuple[str, str | None]:
    """Parse ``good [bad]``; omit bad to default to HEAD at the git layer.

    Args:
        raw: User input (already stripped by the caller).

    Returns:
        ``(good_ref, bad_ref_or_None)``.

    Raises:
        ValueError: When input is empty or has more than two tokens.
    """
    parts = split_at_most(raw, 2, "good [bad]")
    good = parts[0]
    bad = parts[1] if len(parts) == 2 else None
    return good, bad


def _short_sha(sha: str | None) -> str:
    if not sha:
        return "?"
    return sha[:7]


def _steps_estimate(steps_remaining: int) -> int:
    return math.ceil(math.log2(max(1, steps_remaining)))


class BisectSheet(OptionList):
    """Bottom sheet showing bisect status and start/good/bad/reset controls."""

    keymap_namespace = "bisect"

    def __init__(
        self,
        *,
        git: GitApi,
        on_start: Callable[[], None],
        on_confirm_reset: Callable[[], None],
        on_operation: Callable[[], None] | None = None,
        on_done: Callable[[], None] | None = None,
    ) -> None:
        super().__init__()
        self._git = git
        self._on_start = on_start
        self._on_confirm_reset = on_confirm_reset
        self._on_operation = on_operation
        self._on_done = on_done

    def preferred_sheet_height(self, term_h: int) -> int:
        """Prefer a compact status sheet; host clamps to the sheet max fraction."""
        rows = len(self.content) if self.content else 2
        return min(8, max(4, rows + 2))

    def mount(self) -> None:
        """Mount then load current bisect status into the list."""
        super().mount()
        self._refresh()

    def get_footer_entries(self) -> list[tuple[str, str]]:
        """Hints while the bisect sheet owns the keyboard."""
        return [
            ("s", "Start"),
            ("g", "Good"),
            ("b", "Bad"),
            ("r", "Reset"),
            ("esc", "Close"),
        ]

    def _refresh(self, state: BisectState | None = None) -> None:
        """Rebuild rows from ``state``, reading it fresh when omitted.

        A ``GitError`` (e.g. a drifted interval whose good/bad SHAs no longer
        resolve) degrades the sheet instead of crashing mount or a refresh.
        """
        if state is None:
            try:
                state = self._git.bisect_status()
            except GitError:
                show_toast(
                    "Can't read bisect status",
                    duration=2.0,
                    kind=FeedbackKind.ERROR,
                )
                self.set_content(
                    [
                        "Bisect status unavailable",
                        "run git bisect status in a terminal",
                    ]
                )
                return
        if state is None:
            self.set_content(
                [
                    "No bisect in progress",
                    "press s to start",
                ]
            )
            return
        self.set_content(self._rows_for_state(state))

    def _rows_for_state(self, state: BisectState) -> list[str]:
        current = _short_sha(state.current_head)
        good = _short_sha(state.good_sha)
        bad = _short_sha(state.bad_sha)
        steps = state.steps_remaining
        estimate = _steps_estimate(steps)
        return [
            f"● current commit {current}",
            f"good {good} · bad {bad}",
            f"{steps} commits remain",
            f"~{estimate} steps to go",
        ]

    @bind_action("start", "s", desc="Start bisect", tip="Start")
    def start(self) -> None:
        """Delegate to the app InputLine prompt for good/bad refs."""
        self._on_start()

    @bind_action("good", "g", desc="Mark current commit good", tip="Good")
    def good(self) -> None:
        """Mark HEAD as good and refresh or finish the session."""
        self._mark("good")

    @bind_action("bad", "b", desc="Mark current commit bad", tip="Bad")
    def bad(self) -> None:
        """Mark HEAD as bad and refresh or finish the session."""
        self._mark("bad")

    @bind_action("reset", "r", desc="Reset bisect session", tip="Reset")
    def reset(self) -> None:
        """Ask the app to confirm reset (AlertDialog)."""
        self._on_confirm_reset()

    @bind_action("close", "@", "esc", desc="Close bisect sheet", tip="Close")
    def close(self) -> None:
        """Dismiss the sheet overlay."""
        dismiss_sheet()

    def _mark(self, kind: str) -> None:
        try:
            state = self._git.bisect_status()
        except GitError:
            show_toast(
                "Can't read bisect status",
                duration=2.0,
                kind=FeedbackKind.ERROR,
            )
            return
        if state is None:
            show_toast(
                "No bisect in progress",
                duration=2.0,
                kind=FeedbackKind.WARNING,
            )
            return
        try:
            if kind == "good":
                self._git.bisect_mark_good()
            else:
                self._git.bisect_mark_bad()
        except GitError as exc:
            show_toast(str(exc), duration=3.0, kind=FeedbackKind.ERROR)
            return
        try:
            state = self._git.bisect_status()
        except GitError:
            show_toast(
                "Can't read bisect status",
                duration=2.0,
                kind=FeedbackKind.ERROR,
            )
            self._notify_operation()
            return
        if state is None:
            show_toast(
                "Bisect finished",
                duration=1.5,
                kind=FeedbackKind.SUCCESS,
            )
            self._notify_operation()
            if self._on_done is not None:
                self._on_done()
            return
        show_toast(
            f"Marked {kind}",
            duration=1.5,
            kind=FeedbackKind.SUCCESS,
        )
        self._notify_operation()
        self._refresh(state)

    def _notify_operation(self) -> None:
        """Tell the app a mark moved HEAD so it can refresh panels/header."""
        if self._on_operation is not None:
            self._on_operation()
