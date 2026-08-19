# -*- coding: utf-8 -*-
"""
Module: tests/git/test_git_api.py
Description: Adversarial edge-case tests for the GitApi facade and api/ submodules.
Author: Zev
Date: 2026-08-13
"""

import pytest

from pigit.ext.executor_factory import MockExecutor
from pigit.git import GitApi, GitError, RepoError, SequencerPaused


class TestBindPath:
    def test_returns_new_instance_sharing_executor(self):
        ex = MockExecutor()
        git = GitApi(executor=ex, path="/old")
        git2 = git.bind_path("/new")

        assert git2 is not git
        assert git2.executor is ex
        assert git2.path == "/new"
        # Original instance is untouched.
        assert git.path == "/old"

    def test_path_assignment_propagates_to_submodules(self):
        ex = MockExecutor(
            responses={
                "git symbolic-ref -q --short HEAD || git describe --tags --exact-match": (
                    0,
                    "",
                    "main\n",
                ),
            }
        )
        git = GitApi(executor=ex)
        git.path = "/repo"
        assert git.get_head() == "main"


class TestCoreEdgeCases:
    def test_confirm_repo_nonexistent_dir_returns_empty(self):
        git = GitApi(executor=MockExecutor(), path="/nonexistent")
        assert git.confirm_repo() == ("", "")

    def test_get_git_dir_failure_raises(self):
        git = GitApi(executor=MockExecutor(default=(1, "fatal", "")), path="/repo")
        with pytest.raises(GitError):
            git.get_git_dir()


class TestBranchEdgeCases:
    def test_checkout_failure_raises(self):
        git = GitApi(executor=MockExecutor(default=(1, "error", "")), path="/repo")
        with pytest.raises(GitError):
            git.checkout_branch("feat")

    def test_delete_branch_failure_raises(self):
        git = GitApi(executor=MockExecutor(default=(1, "error", "")), path="/repo")
        with pytest.raises(GitError):
            git.delete_branch("feat")


class TestStashEdgeCases:
    def test_load_stashes_error_returns_empty(self):
        git = GitApi(executor=MockExecutor(default=(1, "error", None)), path="/repo")
        assert git.load_stashes() == []

    def test_stash_pop_failure_raises(self):
        git = GitApi(executor=MockExecutor(default=(1, "conflict", "")), path="/repo")
        with pytest.raises(GitError):
            git.stash_pop("stash@{0}")

    def test_stash_push_includes_untracked(self):
        ex = MockExecutor(default=(0, "", ""))
        git = GitApi(executor=ex, path="/repo")
        git.stash_push()
        assert ex.exec_calls
        assert ex.exec_calls[0][0] == "git stash push -u"

    def test_stash_push_with_message_keeps_untracked_flag(self):
        ex = MockExecutor(default=(0, "", ""))
        git = GitApi(executor=ex, path="/repo")
        git.stash_push(message="wip")
        assert ex.exec_calls[0][0] == "git stash push -u -m wip"


class TestLogGraph:
    def test_load_log_graph_command_shape(self):
        ex = MockExecutor(default=(0, "", "* abc (feat) subject\n"))
        git = GitApi(executor=ex, path="/repo")
        out = git.load_log_graph("feature/x", limit=80)
        assert "* abc (feat) subject" in out
        cmd = ex.exec_calls[0][0]
        assert cmd.startswith("git log --decorate --graph")
        assert "--oneline" not in cmd
        assert "--color=always" in cmd
        assert "--color=never" not in cmd
        assert "-n 80" in cmd
        assert "feature/x" in cmd

    def test_load_log_graph_empty_ref_skips_exec(self):
        ex = MockExecutor(default=(0, "", "nope"))
        git = GitApi(executor=ex, path="/repo")
        assert git.load_log_graph("") == ""
        assert ex.exec_calls == []

    def test_load_log_graph_failure_raises(self):
        ex = MockExecutor(
            default=(128, "fatal: unknown revision 'gone'", ""),
        )
        git = GitApi(executor=ex, path="/repo")
        with pytest.raises(GitError):
            git.load_log_graph("gone")


class TestDiffEdgeCases:
    def test_load_file_diff_error_returns_sentinel(self):
        git = GitApi(executor=MockExecutor(default=(1, "error", None)), path="/repo")
        assert git.load_file_diff("file.py") == "Can't get diff."


class TestWorktreeEdgeCases:
    def test_discard_not_git_repo_raises(self):
        git = GitApi(executor=MockExecutor(), path="/not-a-repo")
        with pytest.raises(RepoError):
            git.discard_file("x.py", tracked=True)


class TestMergeEdgeCases:
    def test_merge_conflict_raises_with_conflict_hint(self):
        git = GitApi(
            executor=MockExecutor(default=(1, "CONFLICT: Merge conflict in x.py", "")),
            path="/repo",
        )
        with pytest.raises(GitError) as exc:
            git.merge("feat")
        assert "conflict" in str(exc.value).lower()

    def test_merge_failure_raises(self):
        git = GitApi(executor=MockExecutor(default=(1, "fatal", "")), path="/repo")
        with pytest.raises(GitError):
            git.merge("feat")


class TestFileioEdgeCases:
    def test_get_file_info_missing_returns_unknown(self):
        git = GitApi(executor=MockExecutor(), path="/repo")
        assert git.get_file_info("missing.py") == ("?", "?")

    def test_hash_object_file_failure_returns_none(self):
        git = GitApi(executor=MockExecutor(default=(1, "error", None)), path="/repo")
        assert git.hash_object_file("file.py") is None


class TestListCommitsInRange:
    def test_parses_commits_oldest_first(self):
        ex = MockExecutor(
            responses={
                'git log --reverse --topo-order --pretty=format:"%H|%P|%s" main..HEAD': (
                    0,
                    "",
                    "aaa1||root commit\nbbb1|aaa1|second commit\nccc1|aaa1 bbb1|merge commit\n",
                )
            }
        )
        git = GitApi(executor=ex, path="/repo")
        commits = git.list_commits_in_range("main")
        assert [c.sha for c in commits] == ["aaa1", "bbb1", "ccc1"]
        assert commits[0].parents == []
        assert commits[0].msg == "root commit"
        assert commits[1].parents == ["aaa1"]
        assert commits[2].is_merge is True

    def test_empty_output_returns_empty(self):
        git = GitApi(executor=MockExecutor(default=(0, "", "")), path="/repo")
        assert git.list_commits_in_range("main") == []

    def test_failed_command_raises(self):
        git = GitApi(
            executor=MockExecutor(default=(1, "fatal: bad revision", "")), path="/repo"
        )
        with pytest.raises(GitError):
            git.list_commits_in_range("nonexistent")


class TestUnstagedChanges:
    def test_has_unstaged_changes_true(self):
        ex = MockExecutor(responses={"git diff --quiet": (1, "", "")})
        git = GitApi(executor=ex, path="/repo")
        assert git.has_unstaged_changes() is True

    def test_has_unstaged_changes_false(self):
        ex = MockExecutor(responses={"git diff --quiet": (0, "", "")})
        git = GitApi(executor=ex, path="/repo")
        assert git.has_unstaged_changes() is False


class TestUntrackedChanges:
    def test_has_untracked_changes_true(self):
        ex = MockExecutor(
            responses={"git ls-files --others --exclude-standard": (0, "", "new.txt\n")}
        )
        git = GitApi(executor=ex, path="/repo")
        assert git.has_untracked_changes() is True

    def test_has_untracked_changes_false(self):
        ex = MockExecutor(
            responses={"git ls-files --others --exclude-standard": (0, "", "")}
        )
        git = GitApi(executor=ex, path="/repo")
        assert git.has_untracked_changes() is False


def test_sequencer_paused_is_git_error():
    assert issubclass(SequencerPaused, GitError)


class TestSequencerDetect:
    def _git(self, tmp_path, *names: str) -> GitApi:
        git_dir = tmp_path / "gitdir"
        git_dir.mkdir()
        for name in names:
            p = git_dir / name
            if name in ("rebase-merge", "rebase-apply"):
                p.mkdir()
            else:
                p.write_text("x\n")
        ex = MockExecutor(
            responses={"git rev-parse --git-dir": (0, "", str(git_dir) + "\n")}
        )
        return GitApi(executor=ex, path=str(tmp_path))

    def test_none_when_clean(self, tmp_path):
        assert self._git(tmp_path).sequencer_in_progress() is None

    def test_merge(self, tmp_path):
        assert self._git(tmp_path, "MERGE_HEAD").sequencer_in_progress() == "merge"

    def test_rebase_merge_dir(self, tmp_path):
        assert self._git(tmp_path, "rebase-merge").sequencer_in_progress() == "rebase"

    def test_cherry_pick(self, tmp_path):
        assert (
            self._git(tmp_path, "CHERRY_PICK_HEAD").sequencer_in_progress()
            == "cherry-pick"
        )

    def test_revert(self, tmp_path):
        assert self._git(tmp_path, "REVERT_HEAD").sequencer_in_progress() == "revert"

    def test_merge_wins_if_multiple(self, tmp_path):
        assert (
            self._git(
                tmp_path, "MERGE_HEAD", "CHERRY_PICK_HEAD"
            ).sequencer_in_progress()
            == "merge"
        )


class TestResolveHeadSha:
    def test_strips_newline(self):
        git = GitApi(
            executor=MockExecutor(
                responses={"git rev-parse HEAD": (0, "", "abc123def\n")}
            ),
            path="/repo",
        )
        assert git.resolve_head_sha() == "abc123def"

    def test_failure_raises(self):
        git = GitApi(executor=MockExecutor(default=(1, "fatal", "")), path="/repo")
        with pytest.raises(GitError):
            git.resolve_head_sha()


class TestHasUnmergedPaths:
    def test_true_when_output(self):
        git = GitApi(
            executor=MockExecutor(
                responses={"git diff --name-only --diff-filter=U": (0, "", "foo.c\n")}
            ),
            path="/repo",
        )
        assert git.has_unmerged_paths() is True

    def test_false_when_empty(self):
        git = GitApi(
            executor=MockExecutor(
                responses={"git diff --name-only --diff-filter=U": (0, "", "")}
            ),
            path="/repo",
        )
        assert git.has_unmerged_paths() is False


class TestCherryPick:
    def test_success_is_silent(self):
        git = GitApi(
            executor=MockExecutor(responses={"git cherry-pick abc": (0, "", "")}),
            path="/repo",
        )
        git.cherry_pick("abc")

    def test_nonzero_without_head_raises_git_error(self, tmp_path):
        git_dir = tmp_path / "g"
        git_dir.mkdir()
        git = GitApi(
            executor=MockExecutor(
                responses={
                    "git cherry-pick abc": (1, "fatal: bad object", ""),
                    "git rev-parse --git-dir": (0, "", str(git_dir) + "\n"),
                }
            ),
            path=str(tmp_path),
        )
        with pytest.raises(GitError) as exc:
            git.cherry_pick("abc")
        assert not isinstance(exc.value, SequencerPaused)

    def test_paused_conflict(self, tmp_path):
        git_dir = tmp_path / "g"
        git_dir.mkdir()
        (git_dir / "CHERRY_PICK_HEAD").write_text("abc\n")
        git = GitApi(
            executor=MockExecutor(
                responses={
                    "git cherry-pick abc": (1, "", "CONFLICT"),
                    "git rev-parse --git-dir": (0, "", str(git_dir) + "\n"),
                    "git diff --name-only --diff-filter=U": (0, "", "a.c\n"),
                }
            ),
            path=str(tmp_path),
        )
        with pytest.raises(SequencerPaused) as exc:
            git.cherry_pick("abc")
        assert exc.value.reason == "conflict"

    def test_paused_empty(self, tmp_path):
        git_dir = tmp_path / "g"
        git_dir.mkdir()
        (git_dir / "CHERRY_PICK_HEAD").write_text("abc\n")
        git = GitApi(
            executor=MockExecutor(
                responses={
                    "git cherry-pick abc": (1, "empty", ""),
                    "git rev-parse --git-dir": (0, "", str(git_dir) + "\n"),
                    "git diff --name-only --diff-filter=U": (0, "", ""),
                }
            ),
            path=str(tmp_path),
        )
        with pytest.raises(SequencerPaused) as exc:
            git.cherry_pick("abc")
        assert exc.value.reason == "empty"

    def test_nested_pick_raises_git_error_not_empty(self, tmp_path):
        """An 'already in progress' stop is not misclassified as an empty pick."""
        git_dir = tmp_path / "g"
        git_dir.mkdir()
        (git_dir / "CHERRY_PICK_HEAD").write_text("abc\n")
        git = GitApi(
            executor=MockExecutor(
                responses={
                    "git cherry-pick abc": (
                        1,
                        "error: cherry-pick is already in progress",
                        "",
                    ),
                    "git rev-parse --git-dir": (0, "", str(git_dir) + "\n"),
                }
            ),
            path=str(tmp_path),
        )
        with pytest.raises(GitError) as exc:
            git.cherry_pick("abc")
        assert "already in progress" in str(exc.value)
