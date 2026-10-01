"""
Module: tests/viewmodels/test_commit_vm.py
Description: CommitViewModel unit tests.
Author: Zev
Date: 2026-05-25
"""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from pigit.app_log_graph import compute_graph_rows
from pigit.git.api import GitError
from pigit.git.model import Branch, Commit
from pigit.viewmodels.commit import CommitViewModel

_COMMITS = [
    Commit("abc1234", "first", "Zev", 1700000000, "pushed", "", [], ["parent1"]),
    Commit("def5678", "second", "Zev", 1700000100, "unpushed", "", [], ["abc1234"]),
]


def _drain(vm) -> list:
    """Run the commit stream synchronously, applying every batch."""
    batches: list = []
    vm._stream_commits(lambda batch: (batches.append(batch), True)[1])
    for batch in batches:
        vm._apply_batch(batch)
    return batches


@pytest.fixture
def commit_vm():
    git = Mock()
    git.get_head.return_value = "main"
    git.load_commits.return_value = _COMMITS
    git.iter_commits.return_value = iter(_COMMITS)
    git.get_remotes.return_value = ["origin"]
    vm = CommitViewModel(git)
    # Simulate _do_load side effects and items population
    commits = git.load_commits.return_value
    vm._items.set(commits)
    from pigit.app_log_graph import compute_graph_rows

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


def test_get_commit_bodies_requests_only_asked_shas(commit_vm):
    commit_vm._git.get_commit_bodies.return_value = {"abc1234": "subject\n\nbody"}
    bodies = commit_vm.get_commit_bodies(["abc1234"])
    assert bodies == {"abc1234": "subject\n\nbody"}
    commit_vm._git.get_commit_bodies.assert_called_once_with(["abc1234"])


def test_init_log_ref_follows_head(commit_vm):
    assert commit_vm.log_ref == "main"


def test_init_detached_uses_HEAD():
    git = Mock()
    git.get_head.return_value = None
    vm = CommitViewModel(git)
    assert vm.log_ref == "HEAD"


def test_stream_reads_the_pinned_ref(commit_vm):
    commit_vm._log_ref = "origin/foo"
    commit_vm._git.iter_commits.return_value = iter([])
    _drain(commit_vm)
    # No configured limit means no ``-n``: the whole ref is read.
    commit_vm._git.iter_commits.assert_called_with("origin/foo", limit=False)


def test_get_commit_bodies_empty_request_is_a_call(commit_vm):
    commit_vm._git.get_commit_bodies.return_value = {}
    assert commit_vm.get_commit_bodies([]) == {}


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


def test_stream_falls_back_when_pinned_ref_dangles(commit_vm):
    commit_vm._git.verify_commitish.side_effect = GitError("bad ref")
    commit_vm._log_ref = "feature"
    commit_vm._git.iter_commits.side_effect = [
        iter([]),  # "feature" is dangling: nothing streams
        iter(_COMMITS),  # fallback to the checkout
    ]

    batches = _drain(commit_vm)

    # Fell back to the cached checkout; the list is HEAD's, not stale.
    assert [b.requested for b in batches] == ["feature"]
    assert batches[0].resolved == "main"
    assert commit_vm.log_ref == "main"


def test_apply_batch_drops_stale_result(commit_vm):
    """Batches for an old ref must not clobber a newer pin."""
    commit_vm._log_ref = "origin/foo"
    stale = _batches_only(commit_vm)[0]
    assert stale.requested == "origin/foo"
    commit_vm._log_ref = "origin/bar"  # user re-pins before the batch lands
    commit_vm._apply_batch(stale)
    assert commit_vm.log_ref == "origin/bar"
    assert list(commit_vm.items.value) == list(_COMMITS)  # untouched


def _batches_only(vm) -> list:
    """Collect the stream's batches without applying them."""
    batches: list = []
    vm._stream_commits(lambda batch: (batches.append(batch), True)[1])
    return batches


def test_first_batch_replaces_and_later_batches_append(commit_vm):
    """A refresh must replace the previous stream's rows, then grow."""
    # A previous stream left three commits on screen.
    old = [Commit(f"old{i}", f"s{i}", "A", i, "", "", []) for i in range(3)]
    commit_vm._items.set(old)
    commit_vm._graph_rows.set(compute_graph_rows(old))

    commits = [Commit(f"{i:04x}", f"s{i}", "A", i, "", "", []) for i in range(3)]
    commit_vm._git.iter_commits.return_value = iter(commits)
    commit_vm.STREAM_BATCH = 2  # two batches: replace, then append

    _drain(commit_vm)

    assert [c.sha for c in commit_vm.items.value] == [c.sha for c in commits]
    assert len(commit_vm.graph_rows) == 3


def test_superseded_stream_stops_pulling(commit_vm):
    """emit() returning False must abandon the generator (closes the pipe)."""
    pulled: list[str] = []

    def _gen():
        for i in range(1000):
            pulled.append(f"{i:04x}")
            yield Commit(f"{i:04x}", "s", "A", i, "", "", [])

    commit_vm.STREAM_BATCH = 10
    commit_vm._git.iter_commits.return_value = _gen()

    commit_vm._stream_commits(lambda batch: False)  # superseded immediately

    # Only the first batch was pulled; the rest of the history is untouched.
    assert len(pulled) == 10


def test_batches_publish_graph_before_items():
    """items subscribers must see graph_rows already updated (row-cache rails)."""
    git = Mock()
    git.get_head.return_value = "main"
    commits = [
        Commit("c", "tip", "Zev", 1, "pushed", "", [], ["b"]),
        Commit("b", "mid", "Zev", 0, "pushed", "", [], ["a"]),
        Commit("a", "root", "Zev", 0, "pushed", "", [], []),
    ]
    git.iter_commits.return_value = iter(commits)
    git.get_remotes.return_value = ["origin"]
    vm = CommitViewModel(git)
    seen: list[tuple[int, int]] = []

    class _Watcher:
        def on_items(self, _value):
            seen.append((len(vm.items.value), len(vm.graph_rows)))

    watcher = _Watcher()
    vm.items.subscribe(watcher.on_items)
    _drain(vm)

    assert seen == [(3, 3)]
    assert vm.graph_rows[0].lanes_after == ["b"]
    assert vm.remotes == ("origin",)


def test_stream_skips_verify_when_commits_present(commit_vm):
    """Auto-refresh must not pay a rev-parse when the ref already resolves."""
    commit_vm._log_ref = "origin/foo"
    commit_vm._git.iter_commits.return_value = iter([commit_vm._items.value[0]])
    _drain(commit_vm)
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


def test_log_limit_caps_the_read(commit_vm):
    """A configured limit becomes ``git log -n``; no limit means no ``-n``."""
    commit_vm._log_limit = 5000
    _drain(commit_vm)
    commit_vm._git.iter_commits.assert_called_with("main", max_commits=5000)


def test_zero_log_limit_reads_everything(commit_vm):
    commit_vm._log_limit = 0
    _drain(commit_vm)
    commit_vm._git.iter_commits.assert_called_with("main", limit=False)
