# -*- coding: utf-8 -*-
"""Tests for advanced TUI features (palette, inspector, contribution graph)."""

from __future__ import annotations

import pytest

from pigit.app_command_palette import CommandPalette
from pigit.app_contribution_graph import ContributionGraph
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
        r.paint(s)
        lines = s.lines()
        # Should draw something (month labels, day labels, cells, legend)
        assert any(c != " " for line in lines for c in line)

    def test_horizontal_layout_16_rows(self):
        """The report fits in 16 rows: heatmap left, line chart right."""
        import datetime

        from pigit.git.model import Commit

        r = ContributionGraph()
        now = int(datetime.datetime.now().timestamp())
        commits = [
            Commit(
                sha=f"{i:08x}",
                msg=f"c{i}",
                author="zev" if i % 3 else "other",
                unix_timestamp=now - i * 86400,
                status="pushed",
                extra_info="",
                tag=[],
            )
            for i in range(400)
        ]
        r.set_commits(commits)
        r.resize((120, 16))
        s = Surface(120, 16)
        r.paint(s)
        rows = ["".join(c.char for c in row) for row in s._rows]
        # Heatmap cells in the left region, line-chart glyphs on the right.
        assert any("■" in row[:59] for row in rows)
        assert any(("─" in row[57:] or "┼" in row[57:]) for row in rows)

    def test_pan_graph_via_mouse(self):
        """Horizontal wheel over the report pans the combined graph."""
        import datetime

        from pigit.git.model import Commit

        r = ContributionGraph()
        now = int(datetime.datetime.now().timestamp())
        r.set_commits(
            [
                Commit(
                    sha=f"{i:08x}",
                    msg=f"c{i}",
                    author="zev",
                    unix_timestamp=now - i * 86400,
                    status="pushed",
                    extra_info="",
                    tag=[],
                )
                for i in range(400)
            ]
        )
        from pigit.termui.mouse import MouseButton, MouseEvent, MouseKind
        from pigit.app_contribution_graph import _PAN_STEP

        r.resize((80, 16))
        right = MouseEvent(2, 3, MouseButton.WHEEL_RIGHT, MouseKind.PRESS)
        assert r.handle_mouse(right) is True
        assert r._pan_x == _PAN_STEP
        left = MouseEvent(2, 3, MouseButton.WHEEL_LEFT, MouseKind.PRESS)
        assert r.handle_mouse(left) is True
        assert r._pan_x == 0
        # Clamped at zero.
        assert r.handle_mouse(left) is True
        assert r._pan_x == 0
