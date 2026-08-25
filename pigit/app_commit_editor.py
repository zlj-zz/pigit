"""
Module: pigit/app_commit_editor.py
Description: Inline commit message editor (Sheet overlay).
Author: Zev
Date: 2026-05-29
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from collections.abc import Callable, Sequence

from pigit.termui import FeedbackKind, keys, palette, show_toast, Component
from pigit.termui.containers import Column, Row
from pigit.termui.theme import get_theme
from pigit.termui.widgets import InputLine, LintBar
from pigit.termui.types import OverlayDispatchResult
from pigit.termui.wcwidth_table import wcswidth
from .app_theme import THEME

if TYPE_CHECKING:
    from pigit.git.model import File
    from pigit.viewmodels.status import IStatusViewModel
    from pigit.termui import Surface


_HANDLED = OverlayDispatchResult.HANDLED_EXPLICIT

# Discoverability for overlay keys (not in Status Help while the sheet owns input).
_SHORTCUT_PAIRS: tuple[tuple[str, str], ...] = (
    ("Tab", "body"),
    ("Ctrl+Enter", "commit"),
    ("Esc", "cancel"),
)


def _shortcut_hints_width(pairs: Sequence[tuple[str, str]] = _SHORTCUT_PAIRS) -> int:
    """Return display width of the shortcut strip including leading gap."""
    parts: list[str] = []
    for i, (key, desc) in enumerate(pairs):
        if i:
            parts.append("  ")
        parts.append(f"{key} {desc}")
    # Leading space separates lint (left) from shortcuts (right).
    return 1 + wcswidth("".join(parts))


class _StagedHeader(Component):
    """One-line static header showing staged file count."""

    def __init__(self, count: int) -> None:
        super().__init__()
        self._count = count

    def paint(self, surface: Surface) -> None:
        text = f"Staged ({self._count})"
        surface.draw_text_rgb(0, 0, text, fg=THEME.fg_dim, bg=THEME.bg_chrome)


class _StagedList(Component):
    """Read-only list of staged files with status indicators."""

    def __init__(
        self,
        files: list[File],
        *,
        id: str | None = None,
    ) -> None:
        super().__init__(id=id)
        self.files = files

    def paint(self, surface: Surface) -> None:
        if not self.files:
            surface.draw_text_rgb(
                0,
                0,
                "  No staged files",
                fg=THEME.fg_dim,
                bg=THEME.bg_chrome,
            )
            return

        max_rows = surface.height
        for i, f in enumerate(self.files[:max_rows]):
            if i >= max_rows:
                break
            staged = f.short_status[0] if len(f.short_status) > 0 else " "
            line = f"  {staged} {f.name}"
            if len(line) > surface.width:
                line = line[: surface.width - 1] + "…"
            fg = THEME.fg_dim
            if staged in "MA":
                fg = THEME.fg_success
            elif staged == "D":
                fg = THEME.fg_danger
            elif staged in "RC":
                fg = THEME.fg_warning
            surface.draw_text_rgb(i, 0, line, fg=fg, bg=THEME.bg_chrome)


class _ShortcutHints(Component):
    """Right-side shortcut strip for the commit editor status bar."""

    WIDTH = _shortcut_hints_width()

    def paint(self, surface: Surface) -> None:
        theme = get_theme()
        surface.fill_rect_rgb(0, 0, surface.width, surface.height, THEME.bg_base)
        col = 1 if surface.width > 0 else 0
        for i, (key, desc) in enumerate(_SHORTCUT_PAIRS):
            if i > 0:
                gap = "  "
                if col + wcswidth(gap) > surface.width:
                    break
                surface.draw_text_rgb(0, col, gap, fg=theme.fg_muted)
                col += wcswidth(gap)
            if col + wcswidth(key) > surface.width:
                break
            surface.draw_text_rgb(
                0,
                col,
                key,
                fg=theme.fg_primary,
                style_flags=palette.STYLE_BOLD,
            )
            col += wcswidth(key)
            desc_text = f" {desc}"
            if col + wcswidth(desc_text) > surface.width:
                break
            surface.draw_text_rgb(0, col, desc_text, fg=theme.fg_muted)
            col += wcswidth(desc_text)


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
        self._shortcut_hints = _ShortcutHints()
        # Bottom status: lint (left, flex) | shortcuts (right, fixed).
        self._status_bar = Row(
            children=[self._lint_bar, self._shortcut_hints],
            widths=["flex", _ShortcutHints.WIDTH],
        )
        self._focus_index = 0  # 0=subject, 1=body

        # Staged files header + list
        self._staged_header = _StagedHeader(len(staged_files))
        self._staged_list = _StagedList(staged_files)

        # Layout: Row -> [Column(editor, flex), Column(staged, flex)]
        # widths are assigned dynamically when Sheet resizes
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

    # -- Component overrides ----------------------------------------------

    @property
    def focus_child(self) -> Component | None:
        """Return the currently focused input."""
        return self._current_input()

    def paint(self, surface: Surface) -> None:
        self._root.paint(surface)

    def resize(self, size: tuple[int, int]) -> None:
        self._size = size
        self._root.resize(size)

    def activate(self) -> None:
        super().activate()
        self._subject.set_value("")
        self._body.set_value("")
        self._status_bar.activate()
        self._staged_header.activate()
        self._staged_list.activate()

    def deactivate(self) -> None:
        super().deactivate()
        self._status_bar.deactivate()
        self._staged_header.deactivate()
        self._staged_list.deactivate()

    # -- Focus management -------------------------------------------------

    def _current_input(self) -> InputLine:
        return self._subject if self._focus_index == 0 else self._body

    # -- Event routing ----------------------------------------------------

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

    # -- Internal ---------------------------------------------------------

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
