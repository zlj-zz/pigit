# -*- coding: utf-8 -*-
"""
Module: tests/observe/test_worktree_paths.py
Description: Tests for worktree denylist and observe path expansion.
Author: Zev
Date: 2026-08-20
"""

from __future__ import annotations

from pathlib import Path

from pigit.observe.denylist import (
    DEFAULT_WORKTREE_DENY_NAMES,
    is_denied_name,
    rel_path_is_denied,
)
from pigit.observe.paths import (
    MAX_WORKTREE_STAT_PATHS,
    build_worktree_observe_paths,
    expand_watch_roots_to_paths,
)
from pigit.observe.types import WatchRoot


def test_denied_names_include_common_build_dirs():
    assert "node_modules" in DEFAULT_WORKTREE_DENY_NAMES
    assert is_denied_name("node_modules")
    assert is_denied_name(".venv")
    assert not is_denied_name("src")


def test_rel_path_denied_when_any_segment_matches():
    assert rel_path_is_denied("node_modules/pkg/index.js")
    assert rel_path_is_denied("pkg/node_modules/x")
    assert not rel_path_is_denied("src/app.py")


def test_build_worktree_paths_skips_deny_and_includes_status(tmp_path: Path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("a\n")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "x").write_text("x\n")
    (tmp_path / "readme.md").write_text("hi\n")
    nested = tmp_path / "src" / "b.py"
    nested.write_text("b\n")

    paths, truncated = build_worktree_observe_paths(
        str(tmp_path),
        status_rel_paths=["src/b.py", "node_modules/x"],
    )
    assert truncated is False
    resolved = {Path(p).resolve() for p in paths}
    assert (tmp_path / "src").resolve() in resolved
    assert (tmp_path / "readme.md").resolve() in resolved
    assert (tmp_path / "src" / "b.py").resolve() in resolved
    assert (tmp_path / "node_modules").resolve() not in resolved
    assert (tmp_path / "node_modules" / "x").resolve() not in resolved


def test_build_worktree_paths_respects_budget(tmp_path: Path):
    for i in range(20):
        (tmp_path / f"f{i}.txt").write_text("x\n")
    paths, truncated = build_worktree_observe_paths(
        str(tmp_path),
        status_rel_paths=[],
        max_paths=5,
    )
    assert truncated is True
    assert len(paths) == 5


def test_expand_watch_roots_includes_worktree(tmp_path: Path):
    (tmp_path / "app.py").write_text("x\n")
    git = tmp_path / ".git"
    git.mkdir()
    (git / "HEAD").write_text("ref: refs/heads/main\n")
    roots = [
        WatchRoot(kind="git_dir", path=str(git)),
        WatchRoot(kind="common_dir", path=str(git)),
        WatchRoot(kind="worktree", path=str(tmp_path)),
    ]
    paths, truncated = expand_watch_roots_to_paths(roots)
    assert truncated is False
    assert any(p.endswith("HEAD") for p in paths)
    assert any(Path(p).name == "app.py" for p in paths)
    assert len(paths) <= MAX_WORKTREE_STAT_PATHS + 20
