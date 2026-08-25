"""
Module: tests/app/test_commit_editor.py
Description: Tests for inline CommitEditor status bar shortcuts.
Author: Zev
Date: 2026-08-21
"""

from __future__ import annotations

from unittest.mock import MagicMock

from pigit.app_commit_editor import (
    CommitEditor,
    _ShortcutHints,
    _SHORTCUT_PAIRS,
    _shortcut_hints_width,
)
from pigit.termui.surface import Surface
from pigit.termui.theme import get_theme


def test_shortcut_hints_width_matches_pairs() -> None:
    assert _ShortcutHints.WIDTH == _shortcut_hints_width(_SHORTCUT_PAIRS)
    assert _ShortcutHints.WIDTH > 20


def test_commit_editor_status_bar_is_lint_plus_shortcuts() -> None:
    editor = CommitEditor(
        vm=MagicMock(),
        staged_files=[],
        on_submit=lambda _msg: None,
        on_cancel=lambda: None,
    )
    assert editor._status_bar.children == [editor._lint_bar, editor._shortcut_hints]
    assert editor._editor_col.children[-1] is editor._status_bar


def test_shortcut_hints_render_keys() -> None:
    hints = _ShortcutHints()
    hints.resize((_ShortcutHints.WIDTH, 1))
    surface = Surface(_ShortcutHints.WIDTH, 1)
    hints.paint(surface)
    # After leading space, first glyph of "Tab"
    cell = surface.rows()[0][1]
    assert cell.char == "T"
    assert cell.fg == get_theme().fg_primary
