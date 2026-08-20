# -*- coding: utf-8 -*-
"""
Module: tests/observe/test_worktree_digest.py
Description: Worktree porcelain digest discovery for clean→Modified.
Author: Zev
Date: 2026-08-20
"""

from __future__ import annotations

from pathlib import Path

from pigit.observe.backend import StatMtimeBackend
from pigit.observe.digest import hash_porcelain
from pigit.observe.types import WatchRoot


def test_hash_porcelain_stable_for_same_text():
    assert hash_porcelain(" M a.py\n") == hash_porcelain(" M a.py\n")
    assert hash_porcelain(" M a.py\n") != hash_porcelain(" M b.py\n")


def test_digest_emits_when_porcelain_changes(tmp_path: Path):
    """Content edits that only bump file mtime still wake via digest."""
    git = tmp_path / ".git"
    git.mkdir()
    (git / "HEAD").write_text("ref: refs/heads/main\n")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("clean\n")

    state = {"text": ""}

    def digest() -> str:
        return hash_porcelain(state["text"])

    backend = StatMtimeBackend(worktree_digest=digest)
    backend.start(
        [
            WatchRoot(kind="git_dir", path=str(git)),
            WatchRoot(kind="common_dir", path=str(git)),
            WatchRoot(kind="worktree", path=str(tmp_path)),
        ]
    )
    assert backend.poll() == []

    state["text"] = " M src/a.py\n"
    signals = backend.poll()
    assert any(Path(s.path).resolve() == tmp_path.resolve() for s in signals)

    assert backend.poll() == []


def test_digest_idle_without_worktree_root(tmp_path: Path):
    git = tmp_path / ".git"
    git.mkdir()
    (git / "HEAD").write_text("ref: refs/heads/main\n")
    calls = {"n": 0}

    def digest() -> str:
        calls["n"] += 1
        return "x"

    backend = StatMtimeBackend(worktree_digest=digest)
    backend.start(
        [
            WatchRoot(kind="git_dir", path=str(git)),
            WatchRoot(kind="common_dir", path=str(git)),
        ]
    )
    backend.poll()
    assert calls["n"] == 0
