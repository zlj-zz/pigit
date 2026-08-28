# -*- coding: utf-8 -*-
"""
Module: tests/git/test_bisect.py
Description: Unit tests for bisect status parsing and mark/start/reset commands.
Author: Zev
Date: 2026-08-28
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pigit.ext.executor_factory import MockExecutor
from pigit.git import GitApi, GitError
from pigit.git.api._bisect import BisectState


def _verify_response(sha: str) -> tuple[int, str, str]:
    return (0, "", f"{sha}\n")


def test_bisect_status_none_without_log(tmp_path: Path):
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    ex = MockExecutor(responses={"git rev-parse --git-dir": (0, "", f"{git_dir}\n")})
    git = GitApi(executor=ex, path=str(tmp_path))
    assert git.bisect_status() is None


def test_bisect_status_parses_log_and_counts(tmp_path: Path):
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    good = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    bad = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
    head = "cccccccccccccccccccccccccccccccccccccccc"
    (git_dir / "BISECT_LOG").write_text(
        f"# bad: [{bad}] tip\n"
        f"# good: [{good}] base\n"
        f"git bisect start '{bad}' '{good}'\n",
        encoding="utf-8",
    )
    ex = MockExecutor(
        responses={
            "git rev-parse --git-dir": (0, "", f"{git_dir}\n"),
            f"git rev-parse --verify --end-of-options 'HEAD^{{commit}}'": (
                _verify_response(head)
            ),
            f"git rev-list --count {good}..{bad}": (0, "", "4\n"),
        }
    )
    git = GitApi(executor=ex, path=str(tmp_path))
    state = git.bisect_status()
    assert state == BisectState(
        good_sha=good,
        bad_sha=bad,
        current_head=head,
        steps_remaining=4,
    )


def test_bisect_status_uses_latest_good_bad_marks(tmp_path: Path):
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    (git_dir / "BISECT_LOG").write_text(
        "# bad: [1111111111111111111111111111111111111111] old\n"
        "# good: [2222222222222222222222222222222222222222] old\n"
        "# bad: [3333333333333333333333333333333333333333] new\n"
        "# good: [4444444444444444444444444444444444444444] new\n",
        encoding="utf-8",
    )
    head = "5555555555555555555555555555555555555555"
    good = "4444444444444444444444444444444444444444"
    bad = "3333333333333333333333333333333333333333"
    ex = MockExecutor(
        responses={
            "git rev-parse --git-dir": (0, "", f"{git_dir}\n"),
            f"git rev-parse --verify --end-of-options 'HEAD^{{commit}}'": (
                _verify_response(head)
            ),
            f"git rev-list --count {good}..{bad}": (0, "", "2\n"),
        }
    )
    git = GitApi(executor=ex, path=str(tmp_path))
    state = git.bisect_status()
    assert state is not None
    assert state.good_sha == good
    assert state.bad_sha == bad
    assert state.steps_remaining == 2


def test_bisect_start_resolves_refs_to_sha():
    good = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    bad = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
    ex = MockExecutor(
        responses={
            f"git rev-parse --verify --end-of-options 'v1.0^{{commit}}'": (
                _verify_response(good)
            ),
            f"git rev-parse --verify --end-of-options 'HEAD^{{commit}}'": (
                _verify_response(bad)
            ),
            f"git bisect start {bad} {good}": (0, "", ""),
        }
    )
    git = GitApi(executor=ex, path="/repo")
    git.bisect_start("v1.0")
    cmds = [c[0] for c in ex.exec_calls if isinstance(c[0], str)]
    assert any(cmd.startswith("git bisect start ") for cmd in cmds)
    start = [c for c in cmds if c.startswith("git bisect start ")][-1]
    assert good in start and bad in start


def test_bisect_mark_good_uses_absolute_head_sha():
    sha = "cccccccccccccccccccccccccccccccccccccccc"
    ex = MockExecutor(
        responses={
            f"git rev-parse --verify --end-of-options 'HEAD^{{commit}}'": (
                _verify_response(sha)
            ),
            f"git bisect good {sha}": (0, "", ""),
        }
    )
    git = GitApi(executor=ex, path="/repo")
    git.bisect_mark_good()
    cmds = [c[0] for c in ex.exec_calls if isinstance(c[0], str)]
    assert f"git bisect good {sha}" in cmds


def test_bisect_mark_bad_uses_absolute_head_sha():
    sha = "dddddddddddddddddddddddddddddddddddddddd"
    ex = MockExecutor(
        responses={
            f"git rev-parse --verify --end-of-options 'HEAD^{{commit}}'": (
                _verify_response(sha)
            ),
            f"git bisect bad {sha}": (0, "", ""),
        }
    )
    git = GitApi(executor=ex, path="/repo")
    git.bisect_mark_bad()
    cmds = [c[0] for c in ex.exec_calls if isinstance(c[0], str)]
    assert f"git bisect bad {sha}" in cmds


def test_bisect_reset():
    ex = MockExecutor(responses={"git bisect reset": (0, "", "")})
    git = GitApi(executor=ex, path="/repo")
    git.bisect_reset()
    assert ex.exec_calls[-1][0] == "git bisect reset"


def test_bisect_start_failure_raises():
    good = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    bad = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
    ex = MockExecutor(
        responses={
            f"git rev-parse --verify --end-of-options 'good^{{commit}}'": (
                _verify_response(good)
            ),
            f"git rev-parse --verify --end-of-options 'bad^{{commit}}'": (
                _verify_response(bad)
            ),
            f"git bisect start {bad} {good}": (1, "fatal: already", ""),
        }
    )
    git = GitApi(executor=ex, path="/repo")
    with pytest.raises(GitError):
        git.bisect_start("good", "bad")
