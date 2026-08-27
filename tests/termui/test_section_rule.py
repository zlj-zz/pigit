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


def test_section_rule_paints_fill_label_tail():
    theme = get_theme()
    lst = OptionList(content=["a"], size=(24, 4), header=SectionRule("Status"))
    lst.resize((24, 4))
    surface = Surface(24, 4)
    lst.paint(surface)
    row = "".join(c.char for c in surface.rows()[0]).rstrip("\x00").rstrip()
    assert row.endswith("Status ──")
    assert "─" in row
    label_start = row.index("Status")
    for col in range(label_start, label_start + 6):
        assert surface.rows()[0][col].style_flags & palette.STYLE_BOLD
        assert surface.rows()[0][col].fg == theme.fg_panel_title


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
