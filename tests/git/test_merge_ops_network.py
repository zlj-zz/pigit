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


def test_push_set_upstream_runs_dash_u_with_terminal_prompt_disabled() -> None:
    ex = MockExecutor(default=(0, "", ""))
    git = GitApi(executor=ex, path="/repo")
    git.push_set_upstream("origin", "feature/fxk_api_count")
    cmd, _flags, kws = ex.exec_calls[-1]
    assert cmd == "git push -u origin feature/fxk_api_count"
    assert kws.get("env", {}).get("GIT_TERMINAL_PROMPT") == "0"


def test_has_upstream_true_when_rev_parse_ok() -> None:
    ex = MockExecutor(
        responses={"git rev-parse --abbrev-ref @{upstream}": (0, "", "origin/dev\n")}
    )
    git = GitApi(executor=ex, path="/repo")
    assert git.has_upstream() is True


def test_has_upstream_false_when_rev_parse_fails() -> None:
    ex = MockExecutor(
        responses={"git rev-parse --abbrev-ref @{upstream}": (128, "fatal", "")}
    )
    git = GitApi(executor=ex, path="/repo")
    assert git.has_upstream() is False


def test_get_current_branch_none_when_detached() -> None:
    ex = MockExecutor(responses={"git symbolic-ref -q --short HEAD": (1, "", "")})
    git = GitApi(executor=ex, path="/repo")
    assert git.get_current_branch() is None


def test_default_push_remote_prefers_origin() -> None:
    ex = MockExecutor(responses={"git remote show": (0, "", "upstream\norigin\n")})
    git = GitApi(executor=ex, path="/repo")
    assert git.default_push_remote() == "origin"


def test_default_push_remote_falls_back_to_first() -> None:
    ex = MockExecutor(responses={"git remote show": (0, "", "fork\n")})
    git = GitApi(executor=ex, path="/repo")
    assert git.default_push_remote() == "fork"


def test_default_push_remote_none_when_empty() -> None:
    ex = MockExecutor(responses={"git remote show": (0, "", "")})
    git = GitApi(executor=ex, path="/repo")
    assert git.default_push_remote() is None


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


def test_hard_reset_head_runs_git_reset_hard() -> None:
    ex = MockExecutor(default=(0, "", ""))
    git = GitApi(executor=ex, path="/repo")
    git.hard_reset_head("0123456789abcdef")
    cmd, _flags, _kws = ex.exec_calls[-1]
    assert cmd == "git reset --hard 0123456789abcdef"


def test_hard_reset_head_failure_raises_git_error() -> None:
    ex = MockExecutor(default=(1, "fatal: bad revision", ""))
    git = GitApi(executor=ex, path="/repo")
    with pytest.raises(GitError, match="bad revision"):
        git.hard_reset_head("nope")
