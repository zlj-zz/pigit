# -*- coding: utf-8 -*-
"""
Module: tests/git/test_worktrees.py
Description: Unit tests for git worktree list/add/remove and porcelain parsing.
Author: Zev
Date: 2026-08-28
"""

from __future__ import annotations

import pytest

from pigit.ext.executor_factory import MockExecutor
from pigit.git import GitApi, GitError
from pigit.git.api._worktrees import WorktreeInfo, parse_worktree_porcelain

PORCELAIN_BRANCHED = """\
worktree /repo
HEAD abc111
branch refs/heads/main

worktree /repo-feat
HEAD def222
branch refs/heads/feat/x
"""

PORCELAIN_DETACHED_LINE = """\
worktree /repo
HEAD abc111
branch refs/heads/main

worktree /repo-d
HEAD def222
detached
"""

PORCELAIN_DETACHED_NO_BRANCH = """\
worktree /repo
HEAD abc111
branch refs/heads/main

worktree /repo-d
HEAD def222
"""


def test_parse_porcelain_branched_and_main():
    rows = parse_worktree_porcelain(PORCELAIN_BRANCHED)
    assert len(rows) == 2
    assert rows[0] == WorktreeInfo(
        path="/repo",
        head_sha="abc111",
        branch="main",
        is_main=True,
        detached=False,
    )
    assert rows[1].path == "/repo-feat"
    assert rows[1].branch == "feat/x"
    assert rows[1].is_main is False
    assert rows[1].detached is False


def test_parse_porcelain_explicit_detached_line():
    rows = parse_worktree_porcelain(PORCELAIN_DETACHED_LINE)
    assert rows[1].detached is True
    assert rows[1].branch is None
    assert rows[1].head_sha == "def222"


def test_parse_porcelain_missing_branch_is_detached():
    rows = parse_worktree_porcelain(PORCELAIN_DETACHED_NO_BRANCH)
    assert rows[1].detached is True
    assert rows[1].branch is None


def test_list_worktrees_uses_porcelain():
    ex = MockExecutor(
        responses={"git worktree list --porcelain": (0, "", PORCELAIN_BRANCHED)}
    )
    git = GitApi(executor=ex, path="/repo")
    rows = git.list_worktrees()
    assert [r.path for r in rows] == ["/repo", "/repo-feat"]


def test_list_worktrees_failure_raises():
    git = GitApi(executor=MockExecutor(default=(1, "fatal", "")), path="/repo")
    with pytest.raises(GitError):
        git.list_worktrees()


def test_add_worktree_new_branch_uses_dash_b():
    ex = MockExecutor(default=(0, "", ""))
    git = GitApi(executor=ex, path="/repo")
    git.add_worktree("/tmp/wt", "feat/n", new=True)
    cmd = ex.exec_calls[-1][0]
    assert isinstance(cmd, str)
    assert "git worktree add -b" in cmd
    assert "feat/n" in cmd
    assert "/tmp/wt" in cmd


def test_add_worktree_existing_branch_omits_dash_b():
    ex = MockExecutor(default=(0, "", ""))
    git = GitApi(executor=ex, path="/repo")
    git.add_worktree("/tmp/wt", "main", new=False)
    cmd = ex.exec_calls[-1][0]
    assert isinstance(cmd, str)
    assert "git worktree add -b" not in cmd
    assert cmd.startswith("git worktree add ")


def test_remove_worktree_force_flag():
    ex = MockExecutor(default=(0, "", ""))
    git = GitApi(executor=ex, path="/repo")
    git.remove_worktree("/tmp/wt", force=True)
    cmd = ex.exec_calls[-1][0]
    assert isinstance(cmd, str)
    assert "git worktree remove --force" in cmd


def test_is_worktree_detects_linked_git_dir():
    ex = MockExecutor(
        responses={
            "git rev-parse --git-dir": (
                0,
                "",
                "/repo/.git/worktrees/feat\n",
            ),
            "git rev-parse --git-common-dir": (0, "", "/repo/.git\n"),
        }
    )
    git = GitApi(executor=ex, path="/repo-feat")
    assert git.is_worktree() is True


def test_is_worktree_false_for_main():
    ex = MockExecutor(
        responses={
            "git rev-parse --git-dir": (0, "", "/repo/.git\n"),
            "git rev-parse --git-common-dir": (0, "", "/repo/.git\n"),
        }
    )
    git = GitApi(executor=ex, path="/repo")
    assert git.is_worktree() is False


def test_is_worktree_main_under_worktrees_dir_not_misdetected():
    """A main tree whose path contains a ``worktrees`` segment is not linked.

    Regression for the old string-match check, which misfired when the main
    repo itself lived under a directory named ``worktrees``.
    """
    ex = MockExecutor(
        responses={
            "git rev-parse --git-dir": (0, "", "/home/worktrees/repo/.git\n"),
            "git rev-parse --git-common-dir": (0, "", "/home/worktrees/repo/.git\n"),
        }
    )
    git = GitApi(executor=ex, path="/home/worktrees/repo")
    assert git.is_worktree() is False
