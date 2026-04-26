# -*- coding: utf-8 -*-
"""Tests for advanced TUI features (palette, inspector, contribution graph)."""

from __future__ import annotations

import pytest

from pigit.app_palette import CommandPalette
from pigit.app_inspector import InspectorPanel
from pigit.app_contribution_graph import ContributionGraph
from pigit.termui._surface import Surface


class TestCommandPalette:
    def test_init(self):
        p = CommandPalette()
        assert not p.is_active
        assert p._value == ""

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
        p.on_key("s")
        p.on_key("t")
        assert len(p._candidates) > 0
        assert "status" in p._candidates

    def test_enter_executes(self):
        executed = []
        p = CommandPalette(on_execute=lambda cmd: executed.append(cmd))
        p.open()
        p.on_key("s")
        p.on_key("t")
        p.on_key("a")
        p.on_key("t")
        p.on_key("u")
        p.on_key("s")
        p.on_key("enter")  # enter
        assert len(executed) == 1
        assert executed[0] == "status"

    def test_esc_closes(self):
        p = CommandPalette()
        p.open()
        assert p.is_active
        from pigit.termui import keys

        p.on_key(keys.KEY_ESC)
        assert not p.is_active

    def test_render_inactive(self):
        p = CommandPalette()
        s = Surface(20, 5)
        p._render_surface(s)
        # Should not crash when inactive

    def test_render_active(self):
        p = CommandPalette()
        p.open()
        s = Surface(20, 5)
        p.resize((20, 5))
        p._render_surface(s)
        # Should draw prompt
        lines = s.lines()
        assert ">" in lines[-1]


class TestInspectorPanel:
    def test_init(self):
        i = InspectorPanel()
        assert i._content == []

    def test_show_file(self):
        i = InspectorPanel()
        from pigit.git.model import File

        f = File(
            name="test.py",
            display_str="test.py",
            short_status="M ",
            has_staged_change=True,
            has_unstaged_change=False,
            tracked=True,
            deleted=False,
            added=False,
            has_merged_conflicts=False,
            has_inline_merged_conflicts=False,
        )
        i.show_file(f)
        assert "test.py" in i._content[0]
        assert "staged" in i._content[2]

    def test_render(self):
        i = InspectorPanel()
        from pigit.git.model import File

        f = File(
            name="test.py",
            display_str="test.py",
            short_status="M ",
            has_staged_change=True,
            has_unstaged_change=False,
            tracked=True,
            deleted=False,
            added=False,
            has_merged_conflicts=False,
            has_inline_merged_conflicts=False,
        )
        i.show_file(f)
        s = Surface(20, 10)
        i.resize((20, 10))
        i._render_surface(s)
        text = "\n".join(s.lines())
        assert "test.py" in text


class TestContributionGraph:
    def test_init(self):
        r = ContributionGraph()
        assert r._day_counts == {}
        assert r._max_count == 0

    def test_set_commits(self):
        r = ContributionGraph()
        from pigit.git.model import Commit

        commits = [
            Commit(
                sha="abc1234",
                msg="first",
                author="a",
                unix_timestamp=1000000000,
                status="pushed",
                extra_info="",
                tag=[],
            ),
            Commit(
                sha="def5678",
                msg="second",
                author="a",
                unix_timestamp=1000864000,
                status="pushed",
                extra_info="",
                tag=[],
            ),
        ]
        r.set_commits(commits)
        assert len(r._day_counts) == 2
        assert r._max_count == 1

    def test_render(self):
        r = ContributionGraph()
        from pigit.git.model import Commit

        commits = [
            Commit(
                sha="a",
                msg="1",
                author="a",
                unix_timestamp=1000,
                status="pushed",
                extra_info="",
                tag=[],
            ),
        ]
        r.set_commits(commits)
        s = Surface(60, 12)
        r.resize((60, 12))
        r._render_surface(s)
        lines = s.lines()
        # Should draw something (month labels, day labels, cells, legend)
        assert any(c != " " for line in lines for c in line)
