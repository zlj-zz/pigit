# -*- coding: utf-8 -*-
"""
Module: tests/git/test_merge_ops_network.py
Description: Tests for non-interactive GitApi.push / pull.
Author: Zev
Date: 2026-08-21
"""

from __future__ import annotations

import pytest

from pigit.ext.executor_factory import MockExecutor
from pigit.git import GitApi, GitError


def test_push_runs_git_push_with_terminal_prompt_disabled() -> None:
    ex = MockExecutor(default=(0, "", ""))
    git = GitApi(executor=ex, path="/repo")
    git.push()
    assert ex.exec_calls
    cmd, _flags, kws = ex.exec_calls[-1]
    assert cmd == "git push"
    assert kws.get("env", {}).get("GIT_TERMINAL_PROMPT") == "0"


def test_pull_sets_terminal_prompt_disabled() -> None:
    ex = MockExecutor(default=(0, "", ""))
    git = GitApi(executor=ex, path="/repo")
    git.pull()
    cmd, _flags, kws = ex.exec_calls[-1]
    assert cmd == "git pull"
    assert kws.get("env", {}).get("GIT_TERMINAL_PROMPT") == "0"


def test_pull_conflict_raises_git_error_with_conflict_word() -> None:
    ex = MockExecutor(
        default=(1, "CONFLICT (content): merge conflict in a", ""),
    )
    git = GitApi(executor=ex, path="/repo")
    with pytest.raises(GitError, match="[Cc]onflict"):
        git.pull()


def test_push_failure_raises_git_error() -> None:
    ex = MockExecutor(default=(1, "rejected", ""))
    git = GitApi(executor=ex, path="/repo")
    with pytest.raises(GitError, match="rejected"):
        git.push()
