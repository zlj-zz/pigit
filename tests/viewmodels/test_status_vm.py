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


def test_get_inspector_snapshot(status_vm):
    status_vm._git.get_file_info.return_value = ("1.2K", "644")
    status_vm._git.compare_index_worktree.return_value = "differ"
    status_vm._git.unmerged_stages.return_value = []
    status_vm._git.last_commit_for_path.return_value = None
    info = status_vm.get_inspector_snapshot(0)
    assert info is not None
    assert info.identity == "a.py"
    assert info.size == "1.2K"
    assert info.mode == "644"
    assert info.blobs == "index ≠ worktree"


def test_get_stash_snapshot_memoizes_same_ref(status_vm):
    status_vm._git.stash_meta.return_value = ("Zev", 1700000000, ["abc"])
    status_vm._git.stash_numstat.return_value = ([("a.py", 1, 0)], 1, 0)
    first = status_vm.get_stash_snapshot("stash@{0}")
    second = status_vm.get_stash_snapshot("stash@{0}")
    assert first is second
    assert status_vm._git.stash_meta.call_count == 1
    assert status_vm._git.stash_numstat.call_count == 1


def test_stage_indices_mixed_set_stages_only_unstaged(status_vm):
    """Unstaged + fully staged → add the unstaged file only; do not reset the staged one."""
    result = status_vm.stage_indices({0, 1})
    assert result.success is True
    assert "Updated 1 file(s)" in result.message
    assert status_vm._git.switch_file_status.call_count == 1
    staged = status_vm._git.switch_file_status.call_args[0][0]
    assert staged.name == "a.py"


def test_stage_indices_all_staged_unstages_all(status_vm):
    result = status_vm.stage_indices({1})
    assert result.success is True
    assert "Updated 1 file(s)" in result.message
    status_vm._git.switch_file_status.assert_called_once()
    assert status_vm._git.switch_file_status.call_args[0][0].name == "b.py"


def test_stage_indices_two_staged_unstages_both(status_vm):
    status_vm._items.set(
        [
            status_vm._items.value[1],
            File(
                "d.py",
                "d.py",
                "M ",
                True,
                False,
                True,
                False,
                False,
                False,
                False,
            ),
        ]
    )
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


def test_do_load_bypasses_status_cache(status_vm):
    """Observe-driven refresh must not reuse index/HEAD-keyed status cache."""
    status_vm._do_load()
    status_vm._git.load_status.assert_called_with(use_cache=False)


def test_load_diff_by_path_finds_file_after_reorder(status_vm):
    """Preview identity is path; index may drift after status refresh."""
    from pigit.git.model import File

    status_vm._git.load_file_diff.return_value = "diff a\n"
    # Reorder so a.py is no longer at index 0.
    status_vm._items.set(
        [
            File(
                "b.py",
                "b.py",
                " M",
                False,
                True,
                True,
                False,
                False,
                False,
                False,
            ),
            File(
                "a.py",
                "a.py",
                " M",
                False,
                True,
                True,
                False,
                False,
                False,
                False,
            ),
        ]
    )
    diff = status_vm.load_diff_by_path("a.py")
    assert diff == ["diff a"]
    status_vm._git.load_file_diff.assert_called_with("a.py", True, False, plain=True)


def test_load_diff_by_path_missing_returns_empty(status_vm):
    assert status_vm.load_diff_by_path("nope.py") == []


def test_amend_calls_git_amend_head(status_vm):
    result = status_vm.amend()
    assert result.success is True
    assert result.should_refresh is True
    status_vm._git.amend_head.assert_called_once_with()


def test_amend_failure(status_vm):
    status_vm._git.amend_head.side_effect = RuntimeError("amend failed")
    result = status_vm.amend()
    assert result.success is False
    assert "amend failed" in result.message


def test_stash_push_passes_message(status_vm):
    result = status_vm.stash_push("wip")
    assert result.success is True
    assert result.message == "Stashed"
    status_vm._git.stash_push.assert_called_once_with(message="wip")


def test_stash_apply_keeps_entry(status_vm):
    result = status_vm.stash_apply("stash@{0}")
    assert result.success is True
    assert result.message == "Applied stash"
    status_vm._git.stash_apply.assert_called_once_with("stash@{0}")
    status_vm._git.stash_pop.assert_not_called()
