"""
Module: tests/termui/test_help_format.py
Description: Tests for shared Help / Welcome binding row formatting.
Author: Zev
Date: 2026-08-28
"""

from __future__ import annotations

from pigit.termui.bindings import ExecutableBinding
from pigit.termui.widgets.help_format import (
    build_binding_browser_lines,
    format_binding_group_rows,
)


def _row(keys: str, desc: str, action: str = "test") -> ExecutableBinding:
    return ExecutableBinding(
        keys_display=keys,
        desc=desc,
        action=action,
        owner=object(),
        invoke=lambda: None,
    )


def test_format_binding_group_rows_uses_help_headers():
    groups = [("Global", [_row("?", "Toggle help")])]
    rows = format_binding_group_rows(groups, inner_width=40)
    text = " ".join(seg.text for row in rows for seg in row)
    assert "[Global]" in text
    assert "?" in text
    assert "Toggle help" in text


def test_build_binding_browser_lines_marks_selectable_with_cursor():
    groups = [("Global", [_row("Q", "Quit")])]
    lines = build_binding_browser_lines(groups, inner_width=40, show_cursor=True)
    selectable = [sel for _seg, sel in lines if sel is not None]
    assert selectable == [0]


def test_wrapped_desc_only_first_line_is_selectable():
    groups = [
        ("Global", [_row("?", "Toggle help with a long wrapped description here")])
    ]
    lines = build_binding_browser_lines(groups, inner_width=20, show_cursor=True)
    selectable = [sel for _seg, sel in lines if sel is not None]
    assert selectable == [0]
