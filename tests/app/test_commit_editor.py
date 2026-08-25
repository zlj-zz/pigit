# -*- coding: utf-8 -*-
"""
Module: tests/app/test_commit_editor.py
Description: Tests for inline CommitEditor status bar shortcuts.
Author: Zev
Date: 2026-08-21
"""

from __future__ import annotations

from unittest.mock import MagicMock

from pigit.app_commit_editor import CommitEditor, _SHORTCUT_PAIRS
from pigit.termui.surface import Surface
from pigit.termui.theme import get_theme
from pigit.termui.widgets import ShortcutHints, measure_shortcut_hints


def test_shortcut_hints_width_matches_pairs() -> None:
    hints = ShortcutHints(_SHORTCUT_PAIRS)
    assert hints.preferred_width == measure_shortcut_hints(_SHORTCUT_PAIRS)
    assert hints.preferred_width > 20


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
    hints = ShortcutHints(_SHORTCUT_PAIRS)
    hints.resize((hints.preferred_width, 1))
    surface = Surface(hints.preferred_width, 1)
    hints.paint(surface)
    cell = surface.rows()[0][1]
    assert cell.char == "T"
    assert cell.fg == get_theme().fg_primary


def test_commit_editor_uses_label_and_static_list() -> None:
    from pigit.termui.widgets import Label, StaticList

    editor = CommitEditor(
        vm=MagicMock(),
        staged_files=[],
        on_submit=lambda _msg: None,
        on_cancel=lambda: None,
    )
    assert isinstance(editor._staged_header, Label)
    assert isinstance(editor._staged_list, StaticList)
