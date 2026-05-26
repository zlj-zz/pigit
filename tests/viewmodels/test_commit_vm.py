"""
Module: tests/viewmodels/test_commit_vm.py
Description: CommitViewModel unit tests.
Author: Zev
Date: 2026-05-25
"""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from pigit.git.model import Commit
from pigit.viewmodels.commit import CommitViewModel


@pytest.fixture
def commit_vm():
    git = Mock()
    git.get_head.return_value = "main"
    git.load_commits.return_value = [
        Commit("abc1234", "first", "Zev", 1700000000, "pushed", "", [], ["parent1"]),
        Commit("def5678", "second", "Zev", 1700000100, "unpushed", "", [], ["abc1234"]),
    ]
    git.get_remotes.return_value = ["origin"]
    vm = CommitViewModel(git)
    # Simulate _do_load side effects and items population
    commits = git.load_commits.return_value
    vm._items.set(commits)
    from pigit.app_commit_graph import compute_graph_rows

    vm._graph_rows.set(compute_graph_rows(commits))
    vm._remotes.set(("origin",))
    return vm


def test_graph_rows_populated(commit_vm):
    assert len(commit_vm.graph_rows) == 2


def test_remotes_populated(commit_vm):
    assert commit_vm.remotes == ("origin",)


def test_get_inspector_data(commit_vm):
    commit_vm._git.get_commit_stats.return_value = ([("a.py", 10, 5)], 10, 5)
    info = commit_vm.get_inspector_data(0)
    assert info is not None
    assert info.commit.sha == "abc1234"
    assert info.changed_files == [("a.py", 10, 5)]
    assert info.total_add == 10
    assert info.total_del == 5


def test_get_inspector_data_invalid_index(commit_vm):
    assert commit_vm.get_inspector_data(99) is None


def test_load_diff(commit_vm):
    commit_vm._git.load_commit_info.return_value = "line1\nline2\nline3"
    diff = commit_vm.load_diff(0)
    assert diff == ["line1", "line2", "line3"]
    commit_vm._git.load_commit_info.assert_called_once_with("abc1234", plain=True)


def test_load_diff_invalid_index(commit_vm):
    assert commit_vm.load_diff(99) == []


def test_get_bodies_caches_result(commit_vm):
    commit_vm._git.get_commit_bodies.return_value = {"abc1234": "subject\n\nbody"}
    bodies1 = commit_vm.get_bodies()
    bodies2 = commit_vm.get_bodies()
    assert bodies1 is bodies2
    assert bodies1 == {"abc1234": "subject\n\nbody"}
    commit_vm._git.get_commit_bodies.assert_called_once()
