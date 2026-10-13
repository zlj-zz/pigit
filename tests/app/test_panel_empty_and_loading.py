# -*- coding: utf-8 -*-
"""
Module: tests/app/test_panel_empty_and_loading.py
Description: Commit/Branch empty-state wording and first-load skeletons.
Author: Zev
Date: 2026-10-02
"""

from __future__ import annotations

from unittest.mock import Mock

from pigit.app_branch import BranchPanel
from pigit.app_commit import CommitPanel
from pigit.git.model import Branch, Commit
from pigit.termui.reactive import Signal
from pigit.termui.surface import Surface
from pigit.viewmodels.branch import IBranchViewModel
from pigit.viewmodels.commit import ICommitViewModel


def _painted(panel) -> str:
    surface = Surface(80, 12)
    panel.resize((80, 12))
    panel.paint(surface)
    return "\n".join(surface.lines())


def _branch_panel(branches: list[Branch]) -> BranchPanel:
    vm = Mock(spec=IBranchViewModel)
    vm.items = Signal(branches)
    vm.load_error = Signal(None)
    return BranchPanel(vm=vm, get_git=lambda: Mock())


def _commit(*, msg: str = "a commit") -> Commit:
    return Commit("deadbeefaaaa", msg, "A", 0, "pushed", "", [])


def _commit_panel(commits: list[Commit]) -> CommitPanel:
    vm = Mock(spec=ICommitViewModel)
    vm.items = Signal(commits)
    vm.load_error = Signal(None)
    vm.remotes = ()
    vm.graph_rows = []
    return CommitPanel(vm=vm)


def test_an_empty_repository_does_not_blame_the_filter():
    """With no query there was nothing to match against, so "No matching
    commits." describes a filter the user never typed."""
    panel = _commit_panel([])
    panel._all_commits = []
    panel._apply_filter()
    assert [s.text for s in panel.empty_state] == ["No commits yet."]


def test_a_filter_that_matches_nothing_still_says_so():
    panel = _commit_panel([_commit(msg="unrelated")])
    panel._all_commits = [_commit(msg="unrelated")]
    panel._search_query = "zzz"
    panel._apply_filter()
    assert [s.text for s in panel.empty_state] == ["No matching commits."]


def test_a_matching_filter_shows_the_commit():
    panel = _commit_panel([_commit(msg="fix the thing")])
    panel._all_commits = [_commit(msg="fix the thing")]
    panel._search_query = "thing"
    panel._apply_filter()
    assert "fix the thing" in "\n".join(panel.content)


# ── Every panel says it the same way: an empty state, not a row ──


def _centred_line(painted: str, needle: str) -> str:
    return next(line for line in painted.splitlines() if needle in line)


def test_an_empty_branch_list_says_so_as_an_empty_state():
    """Not a row: ``describe_row`` used to return no segments once
    ``branches`` was empty, so a message held in ``content`` painted blank."""
    panel = _branch_panel([])
    panel.mount()
    panel._vm.items.set([], force=True)
    assert panel.content == []
    assert [s.text for s in panel.empty_state] == ["No local branches found."]
    painted = _painted(panel)
    assert "No local branches found." in painted
    assert _centred_line(painted, "No local branches found.").startswith(" ")


def test_an_empty_commit_list_says_so_as_an_empty_state():
    panel = _commit_panel([])
    panel.mount()
    panel._vm.items.set([], force=True)
    assert panel.content == []
    assert [s.text for s in panel.empty_state] == ["No commits yet."]
    painted = _painted(panel)
    assert _centred_line(painted, "No commits yet.").startswith(" ")


# ── First-load skeletons ──


def test_commit_panel_shows_a_skeleton_until_items_arrive():
    """An empty list and a pending load are different states; without this
    the panel renders a blank row that reads as "no commits"."""
    vm = Mock(spec=ICommitViewModel)
    vm.items = Signal([])
    vm.load_error = Signal(None)
    vm.remotes = ()
    vm.graph_rows = []
    panel = CommitPanel(vm=vm)

    panel.mount()
    assert panel.loading is True

    vm.items.set([_commit()], force=True)
    assert panel.loading is False


def test_branch_panel_shows_a_skeleton_until_items_arrive():
    vm = Mock(spec=IBranchViewModel)
    vm.items = Signal([])
    vm.load_error = Signal(None)
    panel = BranchPanel(vm=vm, get_git=lambda: Mock())

    panel.mount()
    assert panel.loading is True

    vm.items.set([Branch("feat", "0", "0", False)], force=True)
    assert panel.loading is False
