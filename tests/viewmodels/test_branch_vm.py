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


def test_checkout_invalid_index(branch_vm):
    result = branch_vm.checkout(99)
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


def test_rename_branch_invalid_index(branch_vm):
    result = branch_vm.rename_branch(99, "x")
    assert result.success is False
    assert "Invalid index" in result.message


def test_get_inspector_data(branch_vm):
    branch_vm._git.get_branch_recent_commit.return_value = ("msg", "Zev")
    branch_vm._git.get_branch_creation_time.return_value = "2 days ago"
    info = branch_vm.get_inspector_data(1)
    assert info is not None
    assert info.branch.name == "feat"
    assert info.recent_msg == "msg"
    assert info.recent_author == "Zev"
    assert info.created == "2 days ago"


def test_get_inspector_data_invalid_index(branch_vm):
    assert branch_vm.get_inspector_data(99) is None


def test_current_branch(branch_vm):
    assert branch_vm.current_branch() == "main"


def test_current_branch_empty():
    git = Mock()
    git.get_head.return_value = None
    vm = BranchViewModel(git)
    assert vm.current_branch() == ""


def test_can_merge_ok(branch_vm):
    branch_vm._git.has_staged_changes.return_value = False
    ok, msg = branch_vm.can_merge()
    assert ok is True
    assert msg == ""


def test_can_merge_blocked(branch_vm):
    branch_vm._git.has_staged_changes.return_value = True
    ok, msg = branch_vm.can_merge()
    assert ok is False
    assert "Uncommitted changes" in msg
