# -*- coding: utf-8 -*-
"""
Module: tests/git/cmds/test_completion.py
Description: Tests for git completion data source.
Author: Zev
Date: 2026-04-15
"""

from pigit.git.cmds._completion_types import CompletionType
from pigit.git.cmds._completion import _git_completion_candidates


def test_git_branch_completion_candidates(monkeypatch):
    class FakeResult:
        returncode = 0
        stdout = "  main\n* feature\n  remotes/origin/dev\n"

    monkeypatch.setattr("subprocess.run", lambda *a, **k: FakeResult())
    assert _git_completion_candidates(CompletionType.BRANCH) == [
        "feature",
        "main",
        "origin/dev",
    ]


def test_git_file_completion_candidates(monkeypatch):
    class FakeStatus:
        returncode = 0
        stdout = " M src/main.py\n?? README.md\n"

    class FakeLs:
        returncode = 0
        stdout = "config.yml\n"

    def fake_run(cmd, **kwargs):
        if cmd[:2] == ["git", "status"]:
            return FakeStatus()
        return FakeLs()

    monkeypatch.setattr("subprocess.run", fake_run)
    result = _git_completion_candidates(CompletionType.FILE)
    assert "src/main.py" in result
    assert "README.md" in result
    assert "config.yml" in result
