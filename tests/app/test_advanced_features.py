# -*- coding: utf-8 -*-
"""Tests for advanced TUI features (palette, inspector, contribution graph)."""

from __future__ import annotations

import pytest

from pigit.app_command_palette import CommandPalette
from pigit.termui.surface import Surface


class TestCommandPalette:
    def test_init(self):
        p = CommandPalette()
        assert not p.is_active
        assert p._input_line.value == ""

    def test_open_close(self):
        p = CommandPalette()
        p.open()
        assert p.is_active
        p.close()
        assert not p.is_active

    def test_typing_updates_candidates(self):
        executed = []
        p = CommandPalette(on_execute=lambda cmd: executed.append(cmd))
        p.open()
        p.handle_key("s")
        p.handle_key("t")
        assert len(p._candidates) > 0
        assert "status" in [c.id for c in p._candidates]

    def test_enter_executes(self):
        executed = []
        p = CommandPalette(on_execute=lambda cmd: executed.append(cmd))
        p.open()
        p.handle_key("s")
        p.handle_key("t")
        p.handle_key("a")
        p.handle_key("t")
        p.handle_key("u")
        p.handle_key("s")
        from pigit.termui import keys

        p.handle_key(keys.KEY_ENTER)
        assert len(executed) == 1
        assert executed[0] == "status"

    def test_open_lists_catalog(self):
        p = CommandPalette()
        p.open()
        assert any(c.id == "status" for c in p._candidates)
        assert any(c.desc for c in p._candidates)

    def test_esc_closes(self):
        p = CommandPalette()
        p.open()
        assert p.is_active
        from pigit.termui import keys

        p.handle_key(keys.KEY_ESC)
        assert not p.is_active

    def test_render_inactive(self):
        p = CommandPalette()
        s = Surface(20, 5)
        p.paint(s)
        # Should not crash when inactive

    def test_render_active(self):
        p = CommandPalette()
        p.open()
        s = Surface(20, 5)
        p.resize((20, 5))
        p.paint(s)
        # Should draw prompt
        lines = s.lines()
        assert ">" in lines[-1]
