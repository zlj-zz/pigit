# -*- coding: utf-8 -*-
"""
Module: tests/termui/test_section_rule.py
Description: Contract tests for SectionRule OptionList header chrome.
Author: Zev
Date: 2026-08-26
"""

from __future__ import annotations

from pigit.termui import palette
from pigit.termui.surface import Surface
from pigit.termui.theme import get_theme
from pigit.termui.widgets import OptionList, SectionRule


def test_section_rule_paints_label_first_then_fill():
    theme = get_theme()
    lst = OptionList(content=["a"], size=(24, 4), header=SectionRule("Status"))
    lst.resize((24, 4))
    surface = Surface(24, 4)
    lst.paint(surface)
    row = "".join(c.char for c in surface.rows()[0]).rstrip("\x00").rstrip()
    assert row.startswith("── Status ")
    assert row.endswith("─")
    label_start = row.index("Status")
    for col in range(label_start, label_start + 6):
        assert surface.rows()[0][col].style_flags & palette.STYLE_BOLD
        assert surface.rows()[0][col].fg == theme.fg_panel_title


def test_section_rule_detail_rides_muted_after_the_label():
    theme = get_theme()
    lst = OptionList(
        content=[f"row {i}" for i in range(24)],
        size=(40, 6),
        header=SectionRule("Status"),
    )
    lst.resize((40, 6))
    lst.curr_no = 1
    surface = Surface(40, 6)
    lst.paint(surface)
    row = "".join(c.char for c in surface.rows()[0]).rstrip()
    assert row.startswith("── Status · 2/24 ")
    detail_col = row.index("· 2/24")
    assert surface.rows()[0][detail_col].fg == theme.fg_muted


def test_section_rule_counter_follows_the_cursor():
    lst = OptionList(
        content=[f"row {i}" for i in range(10)],
        size=(40, 6),
        header=SectionRule("Status"),
    )
    lst.resize((40, 6))
    first = Surface(40, 6)
    lst.paint(first)
    assert "· 1/10 " in "".join(c.char for c in first.rows()[0])

    lst.next()
    surface = Surface(40, 6)
    lst.paint(surface)
    row = "".join(c.char for c in surface.rows()[0])
    assert "· 2/10 " in row

    lst.curr_no = 9
    last = Surface(40, 6)
    lst.paint(last)
    assert "· 10/10 " in "".join(c.char for c in last.rows()[0])


def test_section_rule_counter_counts_items_not_rendered_rows():
    """Expanded commit bodies put several rows behind one item; the cursor
    selects the item, so the denominator must be the item count."""
    lst = OptionList(
        content=["a", "a-body", "", "b", "b-body", "c"],
        size=(40, 6),
        header=SectionRule("Commit"),
    )
    lst.resize((40, 6))
    lst.set_item_starts([0, 3, 5])
    lst.curr_no = 1
    surface = Surface(40, 6)
    lst.paint(surface)
    row = "".join(c.char for c in surface.rows()[0]).rstrip()
    assert row.startswith("── Commit · 2/3 ")


def test_section_rule_status_precedes_detail():
    theme = get_theme()
    lst = OptionList(
        content=[f"row {i}" for i in range(24)],
        size=(40, 6),
        header=SectionRule("Status"),
    )
    lst.resize((40, 6))
    lst._header.set_status("!")
    lst.curr_no = 1
    surface = Surface(40, 6)
    lst.paint(surface)
    row = "".join(c.char for c in surface.rows()[0]).rstrip()
    assert row.startswith("── Status ! · 2/24 ")
    assert surface.rows()[0][row.index("!")].fg == theme.fg_danger


def test_set_detail_does_not_request_a_render(monkeypatch):
    """It is synced from the list's paint, right before the header is drawn;
    a request there would schedule a second, identical frame."""
    from pigit.termui.widgets import section_rule

    calls: list[int] = []
    monkeypatch.setattr(section_rule, "request_render", lambda: calls.append(1))
    rule = SectionRule("Status")

    rule.set_detail("1/2")

    assert calls == []


def test_section_rule_detail_disappears_with_content():
    lst = OptionList(content=["a"], size=(30, 4), header=SectionRule("Status"))
    lst.resize((30, 4))
    before = Surface(30, 4)
    lst.paint(before)
    assert "· 1/1 " in "".join(c.char for c in before.rows()[0])

    lst.set_content([])
    surface = Surface(30, 4)
    lst.paint(surface)
    row = "".join(c.char for c in surface.rows()[0]).rstrip()
    assert "·" not in row


def test_section_rule_follows_parent_presentation():
    from pigit.termui._runtime_context import (
        RuntimeContext,
        _runtime_ctx,
        reset_focus_manager,
        reset_overlay_host,
        set_focus_manager,
        set_overlay_host,
    )
    from pigit.termui.component import Component
    from pigit.termui.root import ComponentRoot

    theme = get_theme()
    lst = OptionList(content=["a"], size=(20, 4), header=SectionRule("Branch"))
    runtime = RuntimeContext()
    token = _runtime_ctx.set(runtime)
    try:
        root = ComponentRoot(lst)
        root.resize((20, 8))
        set_overlay_host(root)
        set_focus_manager(root._focus_manager)
        root._focus_manager.set_focus_chain(lst)
        assert lst._header._rule_fg() == theme.fg_accent

        other = Component()
        root._focus_manager.set_focus_chain(other)
        assert lst._header._rule_fg() == theme.fg_dim
    finally:
        reset_focus_manager()
        reset_overlay_host()
        _runtime_ctx.reset(token)
