# -*- coding: utf-8 -*-
"""
Module: tests/git/test_git_api.py
Description: Adversarial edge-case tests for the GitApi facade and api/ submodules.
Author: Zev
Date: 2026-08-13
"""

import pytest

from pigit.ext.executor_factory import MockExecutor
from pigit.git import GitApi, GitError, RepoError


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
