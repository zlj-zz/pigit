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
from pigit.viewmodels.branch import IBranchViewModel
from pigit.viewmodels.commit import ICommitViewModel


def _commit(*, msg: str = "a commit") -> Commit:
    return Commit("deadbeefaaaa", msg, "A", 0, "pushed", "", [])


def _commit_panel(commits: list[Commit]) -> CommitPanel:
    vm = Mock(spec=ICommitViewModel)
    vm.items = Signal(commits)
    vm.remotes = ()
    vm.graph_rows = []
    return CommitPanel(vm=vm)


def test_an_empty_repository_does_not_blame_the_filter():
    """With no query there was nothing to match against, so "No matching
    commits." describes a filter the user never typed."""
    panel = _commit_panel([])
    panel._all_commits = []
    panel._apply_filter()
    assert panel.content == ["No commits yet."]


def test_a_filter_that_matches_nothing_still_says_so():
    panel = _commit_panel([_commit(msg="unrelated")])
    panel._all_commits = [_commit(msg="unrelated")]
    panel._search_query = "zzz"
    panel._apply_filter()
    assert panel.content == ["No matching commits."]


def test_a_matching_filter_shows_the_commit():
    panel = _commit_panel([_commit(msg="fix the thing")])
    panel._all_commits = [_commit(msg="fix the thing")]
    panel._search_query = "thing"
    panel._apply_filter()
    assert "fix the thing" in "\n".join(panel.content)


# ── First-load skeletons ──


def test_commit_panel_shows_a_skeleton_until_items_arrive():
    """An empty list and a pending load are different states; without this
    the panel renders a blank row that reads as "no commits"."""
    vm = Mock(spec=ICommitViewModel)
    vm.items = Signal([])
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
    panel = BranchPanel(vm=vm, get_git=lambda: Mock())

    panel.mount()
    assert panel.loading is True

    vm.items.set([Branch("feat", "0", "0", False)], force=True)
    assert panel.loading is False
