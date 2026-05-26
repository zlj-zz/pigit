"""
Module: tests/viewmodels/test_protocols.py
Description: Protocol compliance tests via duck-typing.
Author: Zev
Date: 2026-05-25
"""

from __future__ import annotations

from unittest.mock import Mock

from pigit.viewmodels import (
    BranchViewModel,
    CommitViewModel,
    StatusViewModel,
)

BRANCH_REQUIRED = [
    "items",
    "refresh",
    "dispose",
    "scope",
    "set_scope",
    "checkout",
    "create_branch",
    "rename_branch",
    "delete_branch",
    "get_inspector_data",
    "current_branch",
    "can_merge",
]

COMMIT_REQUIRED = [
    "items",
    "refresh",
    "dispose",
    "graph_rows",
    "remotes",
    "get_inspector_data",
    "load_diff",
    "get_bodies",
]

STATUS_REQUIRED = [
    "items",
    "refresh",
    "dispose",
    "repo_path",
    "stage",
    "discard",
    "ignore",
    "checkout_ours",
    "checkout_theirs",
    "load_diff",
    "get_inspector_data",
    "stage_indices",
    "discard_indices",
    "ignore_indices",
]


def _has_all_attrs(obj, attrs):
    return all(hasattr(obj, a) for a in attrs)


def test_status_vm_has_required_attrs():
    vm = StatusViewModel(Mock())
    assert _has_all_attrs(vm, STATUS_REQUIRED)


def test_branch_vm_has_required_attrs():
    vm = BranchViewModel(Mock())
    assert _has_all_attrs(vm, BRANCH_REQUIRED)


def test_commit_vm_has_required_attrs():
    vm = CommitViewModel(Mock())
    assert _has_all_attrs(vm, COMMIT_REQUIRED)
