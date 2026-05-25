"""
Module: tests/viewmodels/test_status_vm.py
Description: StatusViewModel unit tests.
Author: Zev
Date: 2026-05-25
"""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from pigit.git.model import File
from pigit.viewmodels.status import StatusViewModel


@pytest.fixture
def status_vm():
    git = Mock()
    git.path = "/tmp/repo"
    git.load_status.return_value = [
        File("a.py", "a.py", " M", False, True, True, True, False, False, False),
        File("b.py", "b.py", "M ", True, False, True, True, False, False, False),
        File("c.py", "c.py", "UU", True, True, True, True, False, True, True),
    ]
    vm = StatusViewModel(git)
    vm._items.set(vm._git.load_status.return_value)
    return vm


def test_repo_path(status_vm):
    assert status_vm.repo_path == "/tmp/repo"


def test_repo_path_falls_back_to_empty():
    git = Mock()
    git.path = None
    vm = StatusViewModel(git)
    assert vm.repo_path == ""


def test_stage_unstaged_file(status_vm):
    result = status_vm.stage(0)
    assert result.success is True
    assert "Staged a.py" in result.message
    assert result.should_refresh is True


def test_stage_staged_file(status_vm):
    result = status_vm.stage(1)
    assert result.success is True
    assert "Unstaged b.py" in result.message


def test_stage_invalid_index(status_vm):
    result = status_vm.stage(99)
    assert result.success is False
    assert "Invalid index" in result.message


def test_discard(status_vm):
    result = status_vm.discard(0)
    assert result.success is True
    assert "Discarded a.py" in result.message
    status_vm._git.discard_file.assert_called_once()


def test_ignore(status_vm):
    result = status_vm.ignore(0)
    assert result.success is True
    assert "Ignored a.py" in result.message


def test_checkout_ours_guard_no_conflicts(status_vm):
    result = status_vm.checkout_ours(0)
    assert result.success is False
    assert "No conflicts" in result.message


def test_checkout_ours_success(status_vm):
    result = status_vm.checkout_ours(2)
    assert result.success is True
    assert result.message == "Ours"
    status_vm._git.checkout_ours.assert_called_once()
    status_vm._git.add_file.assert_called_once()


def test_checkout_theirs_guard_no_conflicts(status_vm):
    result = status_vm.checkout_theirs(0)
    assert result.success is False
    assert "No conflicts" in result.message


def test_checkout_theirs_success(status_vm):
    result = status_vm.checkout_theirs(2)
    assert result.success is True
    assert result.message == "Theirs"


def test_get_inspector_data(status_vm):
    status_vm._git.get_file_info.return_value = ("1.2 KB", "2 days ago")
    info = status_vm.get_inspector_data(0)
    assert info is not None
    assert info.file.name == "a.py"
    assert info.size == "1.2 KB"
    assert info.mtime == "2 days ago"


def test_get_inspector_data_invalid_index(status_vm):
    assert status_vm.get_inspector_data(99) is None


def test_stage_indices(status_vm):
    result = status_vm.stage_indices({0, 1})
    assert result.success is True
    assert "Updated 2 file(s)" in result.message
    assert status_vm._git.switch_file_status.call_count == 2


def test_discard_indices(status_vm):
    result = status_vm.discard_indices({0})
    assert result.success is True
    assert "Discarded 1 file(s)" in result.message


def test_ignore_indices(status_vm):
    result = status_vm.ignore_indices({0, 1})
    assert result.success is True
    assert "Ignored 2 file(s)" in result.message


def test_batch_handles_exception(status_vm):
    status_vm._git.switch_file_status.side_effect = RuntimeError("git error")
    result = status_vm.stage_indices({0, 1})
    assert result.success is False
    assert "git error" in result.message


def test_load_diff(status_vm):
    status_vm._git.load_file_diff.return_value = "+line1\n-line2"
    diff = status_vm.load_diff(0)
    assert diff == ["+line1", "-line2"]
