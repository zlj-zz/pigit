"""
Module: tests/viewmodels/test_branch_vm.py
Description: BranchViewModel unit tests.
Author: Zev
Date: 2026-05-25
"""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from pigit.git.model import Branch
from pigit.viewmodels.branch import BranchViewModel


@pytest.fixture
def branch_vm():
    git = Mock()
    git.load_branches.return_value = [
        Branch("main", "0", "0", True),
        Branch("feat", "2", "1", False),
        Branch("remotes/origin/main", "?", "?", False, is_remote=True),
    ]
    git.get_head.return_value = "main"
    vm = BranchViewModel(git)
    vm._items.set(vm._git.load_branches.return_value)
    return vm


def test_scope_defaults_to_local():
    vm = BranchViewModel(Mock())
    assert vm.scope == "local"


def test_set_scope(branch_vm):
    branch_vm.set_scope("remote")
    assert branch_vm.scope == "remote"


def test_do_load_uses_scope(branch_vm):
    branch_vm.set_scope("remote")
    branch_vm._do_load()
    branch_vm._git.load_branches.assert_called_with(scope="remote")


def test_checkout_success(branch_vm):
    result = branch_vm.checkout(1)
    assert result.success is True
    assert "Switched to feat" in result.message
    assert result.should_refresh is True
    branch_vm._git.checkout_branch.assert_called_once_with("feat")


@pytest.mark.parametrize(
    "method, args",
    [
        ("checkout", (99,)),
        ("rename_branch", (99, "x")),
        ("delete_branch", (99,)),
    ],
    ids=["checkout", "rename_branch", "delete_branch"],
)
def test_invalid_index(branch_vm, method, args):
    result = getattr(branch_vm, method)(*args)
    assert result.success is False
    assert "Invalid index" in result.message


def test_create_branch_success(branch_vm):
    result = branch_vm.create_branch("new-branch")
    assert result.success is True
    assert "Created and switched to new-branch" in result.message
    assert result.should_refresh is True
    branch_vm._git.create_branch.assert_called_once_with("new-branch")


def test_create_branch_failure(branch_vm):
    branch_vm._git.create_branch.side_effect = RuntimeError("already exists")
    result = branch_vm.create_branch("new-branch")
    assert result.success is False
    assert "already exists" in result.message


def test_rename_branch_success(branch_vm):
    result = branch_vm.rename_branch(1, "renamed")
    assert result.success is True
    assert "Renamed to renamed" in result.message
    branch_vm._git.rename_branch.assert_called_once_with("feat", "renamed")


def test_delete_branch_success(branch_vm):
    result = branch_vm.delete_branch(1)
    assert result.success is True
    assert "Deleted feat" in result.message
    assert result.should_refresh is True
    branch_vm._git.delete_branch.assert_called_once_with("feat", force=False)


def test_delete_branch_force(branch_vm):
    result = branch_vm.delete_branch(1, force=True)
    assert result.success is True
    branch_vm._git.delete_branch.assert_called_once_with("feat", force=True)


def test_delete_branch_failure(branch_vm):
    branch_vm._git.delete_branch.side_effect = RuntimeError("not fully merged")
    result = branch_vm.delete_branch(1)
    assert result.success is False
    assert "not fully merged" in result.message


def test_get_inspector_snapshot(branch_vm):
    branch_vm._git.verify_commitish.return_value = "abc1234deadbeef"
    branch_vm._git.get_branch_creation_time.return_value = "2026-01-01"
    branch_vm._git.is_ancestor.return_value = True
    branch_vm._git.get_branch_recent_commit.return_value = ("Add thing", "Zev")
    info = branch_vm.get_inspector_snapshot(1)
    assert info is not None
    assert info.identity == "feat"
    assert info.tip == "abc1234deadbeef"
    assert info.created == "2026-01-01"
    assert info.contained is True
    assert info.current == "no"
    assert info.upstream == "none"
    assert info.ahead == "2"
    assert info.behind == "1"
    assert info.recent_msg == "Add thing"
    assert info.recent_author == "Zev"


def test_get_inspector_snapshot_invalid_index(branch_vm):
    assert branch_vm.get_inspector_snapshot(99) is None


def test_get_inspector_snapshot_memoizes_same_selection(branch_vm):
    branch_vm._git.verify_commitish.return_value = "abc1234deadbeef"
    branch_vm._git.is_ancestor.return_value = True
    branch_vm._git.get_branch_creation_time.return_value = "2026-01-01"
    branch_vm._git.get_branch_recent_commit.return_value = ("Add thing", "Zev")
    first = branch_vm.get_inspector_snapshot(1)
    second = branch_vm.get_inspector_snapshot(1)
    assert first is second
    assert branch_vm._git.verify_commitish.call_count == 1
    assert branch_vm._git.get_branch_recent_commit.call_count == 1


def test_get_inspector_snapshot_dangling_ref_marks_contained_unknown(branch_vm):
    """A ref that fails ancestry resolution must not abort the whole snapshot."""
    from pigit.git.api import GitError

    branch_vm._git.verify_commitish.side_effect = GitError("stale")
    branch_vm._git._branch_sha.return_value = "deadbeef"
    branch_vm._git.get_branch_creation_time.return_value = "?"
    branch_vm._git.get_branch_recent_commit.return_value = ("?", "?")
    info = branch_vm.get_inspector_snapshot(1)
    assert info is not None
    assert info.identity == "feat"
    assert info.tip == "deadbeef"
    assert info.contained is None


def test_get_inspector_snapshot_is_ancestor_failure_marks_unknown(branch_vm):
    from pigit.git.api import GitError

    branch_vm._git.verify_commitish.return_value = "abc1234deadbeef"
    branch_vm._git.is_ancestor.side_effect = GitError("merge-base failed")
    branch_vm._git.get_branch_recent_commit.return_value = ("?", "?")
    info = branch_vm.get_inspector_snapshot(1)
    assert info is not None
    assert info.tip == "abc1234deadbeef"
    assert info.contained is None


def test_current_branch(branch_vm):
    assert branch_vm.current_branch() == "main"


def test_current_branch_empty():
    git = Mock()
    git.get_head.return_value = None
    vm = BranchViewModel(git)
    assert vm.current_branch() == ""


def test_can_merge_ok(branch_vm):
    branch_vm._git.has_staged_changes.return_value = False
    branch_vm._git.has_untracked_changes.return_value = False
    ok, msg = branch_vm.can_merge()
    assert ok is True
    assert msg == ""


def test_can_merge_blocked(branch_vm):
    branch_vm._git.has_staged_changes.return_value = True
    branch_vm._git.has_untracked_changes.return_value = False
    ok, msg = branch_vm.can_merge()
    assert ok is False
    assert "Uncommitted changes" in msg


def test_can_merge_blocked_by_untracked(branch_vm):
    """Untracked files that a merge would overwrite must block the merge."""
    branch_vm._git.has_staged_changes.return_value = False
    branch_vm._git.has_untracked_changes.return_value = True
    ok, msg = branch_vm.can_merge()
    assert ok is False
    assert "Uncommitted changes" in msg


def test_can_rebase_ok(branch_vm):
    branch_vm._git.has_staged_changes.return_value = False
    branch_vm._git.has_unstaged_changes.return_value = False
    branch_vm._git.has_untracked_changes.return_value = False
    ok, msg = branch_vm.can_rebase()
    assert ok is True
    assert msg == ""


def test_can_rebase_blocked_by_unstaged(branch_vm):
    branch_vm._git.has_staged_changes.return_value = False
    branch_vm._git.has_unstaged_changes.return_value = True
    branch_vm._git.has_untracked_changes.return_value = False
    ok, msg = branch_vm.can_rebase()
    assert ok is False
    assert "Uncommitted changes" in msg


def test_can_rebase_blocked_by_untracked(branch_vm):
    """Untracked files that a rebase would overwrite must block the rebase."""
    branch_vm._git.has_staged_changes.return_value = False
    branch_vm._git.has_unstaged_changes.return_value = False
    branch_vm._git.has_untracked_changes.return_value = True
    ok, msg = branch_vm.can_rebase()
    assert ok is False
    assert "Uncommitted changes" in msg


def test_load_log_graph_splits_lines(branch_vm):
    branch_vm._git.load_log_graph.return_value = "* a\n* b\n"
    assert branch_vm.load_log_graph("feat") == ["* a", "* b"]
    # The commit cap stays with GitApi (LOG_GRAPH_LIMIT); the VM forwards no limit.
    branch_vm._git.load_log_graph.assert_called_once_with("feat")


def test_load_log_graph_empty_text(branch_vm):
    branch_vm._git.load_log_graph.return_value = ""
    assert branch_vm.load_log_graph("feat") == []
