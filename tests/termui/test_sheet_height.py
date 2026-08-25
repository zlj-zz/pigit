"""
Module: tests/termui/test_sheet_height.py
Description: Tests for Sheet height resolution and clamping.
Author: Zev
Date: 2026-08-22
"""

from __future__ import annotations

from pigit.termui.component import Component
from pigit.termui.widgets.sheet import (
    DEFAULT_SHEET_HEIGHT,
    Sheet,
)


class _PrefChild(Component):
    def preferred_sheet_height(self, term_h: int) -> int:
        return 20


class _PlainChild(Component):
    pass


def test_resolve_height_uses_preferred_and_default_fraction() -> None:
    # term_h=30 → soft cap 10, preferred 20 → 10
    assert Sheet.resolve_height(_PrefChild(), 30) == 10


def test_resolve_height_respects_higher_max_fraction() -> None:
    assert Sheet.resolve_height(_PrefChild(), 30, max_fraction=0.5) == 15


def test_resolve_height_explicit_height() -> None:
    assert Sheet.resolve_height(_PlainChild(), 24, height=5) == 5


def test_resolve_height_explicit_ignores_max_fraction() -> None:
    # Default soft cap would be 10; explicit 12 must stay (under half=15).
    assert Sheet.resolve_height(_PlainChild(), 30, height=12) == 12


def test_resolve_height_default_when_no_preferred() -> None:
    # term_h=24 → soft cap 8, default 8 → 8
    assert Sheet.resolve_height(_PlainChild(), 24) == DEFAULT_SHEET_HEIGHT


def test_resolve_height_explicit_never_exceeds_half_terminal() -> None:
    assert Sheet.resolve_height(_PlainChild(), 20, height=50) == 10


def test_root_show_sheet_uses_resolved_preferred() -> None:
    from pigit.termui.root import ComponentRoot

    class _Body(Component):
        def paint(self, surface) -> None:
            pass

    root = ComponentRoot(body=_Body())
    root.resize((80, 30))
    sheet = root.show_sheet(_PrefChild())
    assert sheet._target_height == 10
