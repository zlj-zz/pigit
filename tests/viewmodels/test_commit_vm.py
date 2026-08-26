"""
Module: tests/viewmodels/test_commit_vm.py
Description: CommitViewModel unit tests.
Author: Zev
Date: 2026-05-25
"""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from pigit.git.api import GitError
from pigit.git.model import Branch, Commit
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


def test_get_inspector_snapshot(commit_vm):
    commit_vm._git.get_commit_stats.return_value = ([("a.py", 10, 5)], 10, 5)
    info = commit_vm.get_inspector_snapshot(0)
    assert info is not None
    assert info.sha == "abc1234"
    assert info.msg == "first"
    assert info.author == "Zev"
    assert info.status == "pushed"
    assert info.tags == "none"
    assert info.files == [("a.py", 10, 5)]
    assert info.total_add == 10
    assert info.total_del == 5


def test_get_inspector_snapshot_joins_tags(commit_vm):
    commit_vm._items.value[0].tag = ["v1.0", "latest"]
    commit_vm._git.get_commit_stats.return_value = ([], 0, 0)
    info = commit_vm.get_inspector_snapshot(0)
    assert info.tags == "v1.0, latest"


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


def test_init_log_ref_follows_head(commit_vm):
    assert commit_vm.log_ref == "main"


def test_init_detached_uses_HEAD():
    git = Mock()
    git.get_head.return_value = None
    vm = CommitViewModel(git)
    assert vm.log_ref == "HEAD"


def test_load_commits_uses_log_ref_not_head(commit_vm):
    commit_vm._log_ref = "origin/foo"
    commit_vm._git.load_commits.return_value = []
    commit_vm._git.get_remotes.return_value = []
    commit_vm._load_commits()
    commit_vm._git.load_commits.assert_called_with("origin/foo")


def test_get_bodies_uses_log_ref(commit_vm):
    commit_vm._log_ref = "feat"
    commit_vm._git.get_commit_bodies.return_value = {}
    commit_vm.get_bodies()
    commit_vm._git.get_commit_bodies.assert_called_with("feat")


def test_set_log_ref_assigns_and_refresh_without_verify(commit_vm):
    """Validation moved to the async load; set_log_ref only assigns."""
    refreshed = []
    commit_vm.refresh = lambda: refreshed.append(True)
    commit_vm.set_log_ref("  origin/foo  ")
    assert commit_vm.log_ref == "origin/foo"
    assert refreshed == [True]
    commit_vm._git.verify_commitish.assert_not_called()


def test_set_log_ref_empty_is_noop(commit_vm):
    commit_vm.set_log_ref("   ")
    assert commit_vm.log_ref == "main"


def test_follow_head_updates_head_and_log_ref(commit_vm):
    refreshed = []
    commit_vm.refresh = lambda: refreshed.append(True)
    # Pinned to a non-checkout ref first.
    commit_vm.set_log_ref("origin/release-1")
    assert commit_vm.follow_head("feat") is True
    assert commit_vm.log_ref == "feat"
    assert commit_vm.viewing_checkout_log() is True
    assert len(refreshed) == 2  # set_log_ref + follow_head


def test_follow_head_without_pin_is_not_reset(commit_vm):
    assert commit_vm.follow_head("main") is False
    assert commit_vm.log_ref == "main"


def test_load_falls_back_when_pinned_ref_dangles(commit_vm):
    commit_vm._git.verify_commitish.side_effect = GitError("bad ref")
    commit_vm.set_log_ref("feature")
    from unittest.mock import Mock as _Mock

    commit_vm._git.load_commits = _Mock(return_value=[])
    result = commit_vm._load_commits()
    # Fell back to the cached checkout; the list is HEAD's, not stale.
    assert result.requested == "feature"
    assert result.resolved == "main"
    assert commit_vm.log_ref == "feature"  # worker never mutates _log_ref
    commit_vm._apply_load(result)
    assert commit_vm.log_ref == "main"


def test_apply_load_drops_stale_result(commit_vm):
    """A load for an old ref must not clobber a newer pin."""
    commit_vm._log_ref = "origin/foo"
    stale = commit_vm._load_commits()
    assert stale.requested == "origin/foo"
    commit_vm._log_ref = "origin/bar"  # user re-pins before load lands
    commit_vm._apply_load(stale)
    assert commit_vm.log_ref == "origin/bar"


def test_apply_load_publishes_graph_before_items():
    """items subscribers must see graph_rows already updated (row-cache rails)."""
    git = Mock()
    git.get_head.return_value = "main"
    commits = [
        Commit("c", "tip", "Zev", 1, "pushed", "", [], ["b"]),
        Commit("b", "mid", "Zev", 0, "pushed", "", [], ["a"]),
        Commit("a", "root", "Zev", 0, "pushed", "", [], []),
    ]
    git.load_commits.return_value = commits
    git.get_remotes.return_value = ["origin"]
    vm = CommitViewModel(git)
    seen: list[tuple[int, int]] = []

    class _Watcher:
        def on_items(self, _value):
            seen.append((len(vm.items.value), len(vm.graph_rows)))

    watcher = _Watcher()
    vm.items.subscribe(watcher.on_items)
    result = vm._load_commits()
    vm._apply_load(result)

    assert seen == [(3, 3)]
    assert vm.graph_rows[0].lanes_after == ["b"]
    assert vm.remotes == ("origin",)


def test_load_skips_verify_when_commits_present(commit_vm):
    """Auto-refresh must not pay a rev-parse when the ref already resolves."""
    commit_vm._log_ref = "origin/foo"
    commit_vm._git.load_commits.return_value = [commit_vm._items.value[0]]  # non-empty
    commit_vm._load_commits()
    commit_vm._git.verify_commitish.assert_not_called()


def test_dispose_does_not_clear_log_ref(commit_vm):
    commit_vm._log_ref = "feat"
    commit_vm.dispose()
    assert commit_vm.log_ref == "feat"


def test_viewing_checkout_log_HEAD_token(commit_vm):
    commit_vm._log_ref = "HEAD"
    assert commit_vm.viewing_checkout_log() is True


def test_viewing_checkout_log_same_branch(commit_vm):
    commit_vm._log_ref = "main"
    commit_vm._git.get_head.return_value = "main"
    assert commit_vm.viewing_checkout_log() is True


def test_viewing_checkout_log_pinned(commit_vm):
    commit_vm._log_ref = "origin/foo"
    commit_vm._git.get_head.return_value = "main"
    assert commit_vm.viewing_checkout_log() is False


def test_list_log_ref_names_head_first(commit_vm):
    commit_vm._git.load_branches.return_value = [
        Branch("HEAD", "?", "?", False),
        Branch("main", "?", "?", True),
        Branch("origin/foo", "?", "?", False, is_remote=True),
    ]
    assert commit_vm.list_log_ref_names() == ["HEAD", "main", "origin/foo"]
