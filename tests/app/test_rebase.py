# -*- coding: utf-8 -*-
"""
Module: tests/app/test_rebase.py
Description: Tests for the interactive rebase todo panel.
Author: Zev
Date: 2026-08-14
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from pigit.app_rebase import RebasePanel
from pigit.git.model import Commit


def _commit(sha: str, parents: tuple[str, ...] = ()) -> Commit:
    return Commit(
        sha=sha,
        msg=f"subject {sha}",
        author="",
        unix_timestamp=0,
        status="",
        extra_info="",
        tag=[],
        parents=list(parents),
    )


def _panel(
    commits: list[Commit], in_progress: bool = False
) -> tuple[RebasePanel, MagicMock]:
    git = MagicMock()
    git.list_commits_in_range.return_value = commits
    git.sequencer_in_progress.return_value = "rebase" if in_progress else None
    git.is_rebase_in_progress.return_value = in_progress
    git.is_merge_in_progress.return_value = False
    git.path = "/repo"
    panel = RebasePanel(git, "main", on_done=MagicMock())
    return panel, git


class TestRebasePanel:
    def test_activate_loads_commits(self):
        panel, _ = _panel([_commit("a1"), _commit("b1", ("a1",))])
        panel.activate()
        assert [i.sha for i in panel._items] == ["a1", "b1"]
        assert all(i.action == "pick" for i in panel._items)

    def test_activate_rejects_empty(self):
        panel, _ = _panel([])
        with patch("pigit.app_rebase.show_toast") as toast:
            panel.activate()
            toast.assert_called_once()
        panel._on_done.assert_called_once()

    def test_activate_rejects_merge(self):
        panel, _ = _panel([_commit("m1", ("a1", "b1"))])
        with patch("pigit.app_rebase.show_toast") as toast:
            panel.activate()
            toast.assert_called_once()
        panel._on_done.assert_called_once()

    def test_activate_rejects_in_progress(self):
        panel, _ = _panel([_commit("a1")], in_progress=True)
        with patch("pigit.app_rebase.show_toast") as toast:
            panel.activate()
            toast.assert_called_once()
        panel._on_done.assert_called_once()

    def test_squash_first_row_rejected(self):
        panel, _ = _panel([_commit("a1"), _commit("b1")])
        panel.activate()
        panel.curr_no = 0
        panel._set_action("squash")
        assert panel._items[0].action == "pick"

    def test_squash_second_row_ok(self):
        panel, _ = _panel([_commit("a1"), _commit("b1")])
        panel.activate()
        panel.curr_no = 1
        panel._set_action("squash")
        assert panel._items[1].action == "squash"

    def test_move_up_squash_to_top_rejected(self):
        panel, _ = _panel([_commit("a1"), _commit("b1")])
        panel.activate()
        panel._items[1].action = "squash"
        panel.curr_no = 1
        panel._move_up()
        assert panel._items[0].action == "pick"
        assert panel._items[1].action == "squash"

    def test_move_up_and_down(self):
        panel, _ = _panel([_commit("a1"), _commit("b1")])
        panel.activate()
        panel.curr_no = 0
        panel._move_down()
        assert panel._items[0].sha == "b1"
        assert panel.curr_no == 1
        panel._move_up()
        assert panel._items[0].sha == "a1"
        assert panel.curr_no == 0

    def test_move_down_squash_to_top_rejected(self):
        panel, _ = _panel([_commit("a1"), _commit("b1")])
        panel.activate()
        panel._items[1].action = "squash"
        panel.curr_no = 0
        panel._move_down()
        assert panel._items[0].action == "pick"
        assert panel._items[1].action == "squash"

    def test_validate_squash_after_drop(self):
        panel, _ = _panel([_commit("a1"), _commit("b1")])
        panel.activate()
        panel._items[0].action = "drop"
        panel._items[1].action = "squash"
        assert panel._validate() is not None

    def test_validate_ok(self):
        panel, _ = _panel([_commit("a1"), _commit("b1")])
        panel.activate()
        panel._items[1].action = "squash"
        assert panel._validate() is None

    def test_set_drop(self):
        panel, _ = _panel([_commit("a1")])
        panel.activate()
        panel.curr_no = 0
        panel._set_action("drop")
        assert panel._items[0].action == "drop"

    def test_render_reserves_last_row_for_hint(self):
        from pigit.termui.surface import Surface

        panel, _ = _panel([_commit("a1"), _commit("b1")])
        panel.activate()
        panel.resize((120, 5))
        surface = Surface(120, 5)
        panel.paint(surface)
        last_row = "".join(c.char for c in surface._rows[4])
        assert "pick" in last_row and "squash" in last_row

    def test_activate_blocks_when_cherry_pick_in_progress(self):
        panel, git = _panel([_commit("a")])
        git.sequencer_in_progress.return_value = "cherry-pick"
        with patch("pigit.app_rebase.show_toast") as toast:
            panel.activate()
        toast.assert_called()
        panel._on_done.assert_called()
        git.list_commits_in_range.assert_not_called()
