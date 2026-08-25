"""
Module: pigit/app_stash.py
Description: Stash list panel with cursor navigation.
Author: Zev
Date: 2026-05-27
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from collections.abc import Callable

from pigit.termui import (
    EVT_GOTO,
    EVT_SELECTION_CHANGED,
    FeedbackKind,
    bind_action,
    MouseButton,
    MouseEvent,
    MouseKind,
    palette,
    Segment,
    show_badge,
    show_toast,
    Surface,
)
from pigit.termui.wcwidth_table import wcswidth
from pigit.termui.widgets import AlertDialog, ItemList

from .app_diff import DiffType
from .app_theme import THEME
from .viewmodels.base import ActionResult

if TYPE_CHECKING:
    from pigit.git.model import Stash
    from pigit.viewmodels.status import IStatusViewModel


class StashPanel(ItemList):
    """Stash list panel with cursor navigation."""

    CURSOR = "●"
    keymap_namespace = "stash"
    tab_name = "Stash"
    tab_key = "2"
    HEADER_ROWS = 1
    _SECTION_LABEL = "Stash"
    _SECTION_TAIL = "──"

    def __init__(
        self,
        *,
        vm: IStatusViewModel,
        id: str | None = None,
        on_toggle_preview: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(
            empty_state=[
                Segment("  No stashes", fg=THEME.fg_dim),
                Segment("  Press 's' to stash current changes", fg=THEME.fg_dim),
            ],
            id=id,
        )
        self._vm = vm
        self._on_toggle_preview = on_toggle_preview
        self._alert_dialog = AlertDialog(
            inner_width=40,
            on_result=lambda _: None,
        )
        self.stashes: list[Stash] = []

    @property
    def visible_row_count(self) -> int:
        """Viewport rows available for stash entries (excludes section header)."""
        return max(0, self._size[1] - self.HEADER_ROWS)

    def activate(self) -> None:
        super().activate()
        self._load_stashes()

    def _load_stashes(self) -> None:
        self.stashes = self._vm.load_stashes()
        if not self.stashes:
            self.set_content([])
            return
        self.set_content([s.msg for s in self.stashes])
        self.emit(EVT_SELECTION_CHANGED)

    def refresh(self):
        self._load_stashes()

    def _draw_section_header(self, surface: Surface) -> None:
        """Draw ``──── Stash ──`` across the top row."""
        w = surface.width
        if w <= 0 or surface.height <= 0:
            return
        label = self._SECTION_LABEL
        # " Stash ──" — space, bold label, space, two dashes
        suffix = f" {label} {self._SECTION_TAIL}"
        suffix_w = wcswidth(suffix)
        fill_w = max(0, w - suffix_w)
        # Structural rule on transparent panel bg — fg_dim, not divider (GUNMETAL).
        rule_fg = THEME.fg_dim
        if fill_w:
            surface.draw_text_rgb(0, 0, "─" * fill_w, fg=rule_fg)
        col = fill_w
        surface.draw_text_rgb(0, col, " ", fg=rule_fg)
        col += 1
        surface.draw_text_rgb(
            0,
            col,
            label,
            fg=THEME.fg_panel_title,
            style_flags=palette.STYLE_BOLD,
        )
        col += wcswidth(label)
        surface.draw_text_rgb(0, col, f" {self._SECTION_TAIL}", fg=rule_fg)

    def paint(self, surface: Surface) -> None:
        """Section header on row 0; stash rows in the remaining viewport."""
        w = surface.width
        h = surface.height
        if w <= 0 or h <= 0:
            return
        self._draw_section_header(surface)
        if h <= self.HEADER_ROWS:
            return
        sub = surface.subsurface(self.HEADER_ROWS, 0, w, h - self.HEADER_ROWS)
        ItemList.paint(self, sub)

    def handle_mouse(self, event: MouseEvent) -> bool:
        """Ignore clicks on the header row; map remaining rows to list items."""
        if event.kind is not MouseKind.PRESS:
            return False
        if event.button in (MouseButton.WHEEL_UP, MouseButton.WHEEL_DOWN):
            return super().handle_mouse(event)
        if event.button is not MouseButton.LEFT:
            return False
        row0 = event.row - 1
        if row0 < self.HEADER_ROWS:
            return True
        adjusted = MouseEvent(
            col=event.col,
            row=event.row - self.HEADER_ROWS,
            button=event.button,
            kind=event.kind,
            shift=event.shift,
            alt=event.alt,
            ctrl=event.ctrl,
            motion=event.motion,
        )
        return ItemList.handle_mouse(self, adjusted)

    def _current_stash(self) -> Stash | None:
        """Return the stash under the cursor, or None if the list is empty."""
        if not self.stashes:
            return None
        return self.stashes[self.curr_no]

    def _run_on_current(self, op: Callable[[str], ActionResult]) -> None:
        """Run a stash-ref operation on the current row."""
        stash = self._current_stash()
        if stash is None:
            return
        self._handle_result(op(stash.ref))

    @bind_action("next", "j", "down", desc="Navigate stash list", tip="Navigate")
    def next_item(self, step: int = 1) -> None:
        self.next(step)

    @bind_action("previous", "k", "up", desc="Navigate stash list", tip="Navigate")
    def previous_item(self, step: int = 1) -> None:
        self.previous(step)

    @bind_action(
        "view_diff", "enter", desc="View diff for selected stash", tip="View diff"
    )
    def view_diff(self) -> None:
        stash = self._current_stash()
        if stash is None:
            return
        diff_lines = self._vm.load_stash_diff(stash.ref)
        self.emit(
            EVT_GOTO,
            target="diff",
            source=self,
            key=stash.ref,
            content=diff_lines,
            repo_path=self._vm.repo_path,
            diff_type=DiffType.STASH,
        )

    @bind_action("toggle_preview", "ctrl p", desc="Toggle diff preview")
    def toggle_preview(self) -> None:
        """Show or hide the Stash side diff preview on a large screen."""
        if self._on_toggle_preview is not None:
            self._on_toggle_preview()

    def preview_title(self) -> str:
        """Return the diff preview box title for the selected stash."""
        stash = self._current_stash()
        if stash is None:
            return ""
        return f"{stash.msg}  {stash.ref}"

    def preview_lines(self) -> list[str]:
        """Return diff lines for the selected stash."""
        stash = self._current_stash()
        if stash is None:
            return []
        return self._vm.load_stash_diff(stash.ref)

    def preview_diff_type(self) -> DiffType:
        """Return stash diff type for the side preview."""
        return DiffType.STASH

    @bind_action("pop", "p", desc="Pop selected stash onto working tree", tip="Pop")
    def pop(self) -> None:
        self._run_on_current(self._vm.stash_pop)

    @bind_action(
        "apply",
        "a",
        desc="Apply selected stash onto working tree (keep in list)",
        tip="Apply",
    )
    def apply(self) -> None:
        self._run_on_current(self._vm.stash_apply)

    @bind_action(
        "drop", "d", desc="Drop selected stash permanently (irreversible)", tip="Drop"
    )
    def drop(self) -> None:
        """Drop the selected stash after confirmation (irreversible)."""
        stash = self._current_stash()
        if stash is None:
            return

        def on_result(confirmed: bool) -> None:
            if not confirmed:
                return
            self._handle_result(self._vm.stash_drop(stash.ref))

        self._alert_dialog.alert(
            f"Drop stash '{stash.ref}'?", on_result, kind=FeedbackKind.ERROR
        )

    def describe_row(
        self,
        idx: int,
        is_cursor: bool,
        *,
        item_idx: int | None = None,
        sub_row: int = 0,
    ) -> tuple[list[Segment], list[Segment] | None, list[Segment]]:
        if not self.stashes or idx >= len(self.stashes):
            return ([], None, [])
        stash = self.stashes[idx]
        cursor_prefix = self.CURSOR if is_cursor else " "
        fg_primary = self.presentation_fg("primary")
        cursor_flags = palette.STYLE_BOLD if is_cursor else 0

        left = [
            Segment(cursor_prefix, fg=fg_primary, style_flags=cursor_flags),
            Segment(" ", fg=fg_primary),
        ]
        main = [Segment(stash.msg, fg=fg_primary, style_flags=cursor_flags)]
        right = [Segment(stash.ref, fg=self.presentation_fg("muted"))]
        return left, main, right

    def _handle_result(self, result) -> None:
        if result.success:
            show_badge(result.message, duration=1.0, kind=FeedbackKind.SUCCESS)
            self._load_stashes()
        else:
            show_toast(result.message, duration=2.0, kind=FeedbackKind.ERROR)

    def get_help_title(self) -> str:
        return "Stash"

    def get_inspector_snapshot(self):
        """Return a frozen snapshot for the selected stash."""
        stash = self._current_stash()
        if stash is None:
            return None
        return self._vm.get_stash_snapshot(stash.ref)
