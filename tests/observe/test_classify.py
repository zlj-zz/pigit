# -*- coding: utf-8 -*-
"""
Module: tests/observe/test_classify.py
Description: Unit tests for observe path classification.
Author: Zev
Date: 2026-08-20
"""

from __future__ import annotations

from pigit.observe.classify import classify_path_signal
from pigit.observe.types import ChangeKind, ObserveContext, PathSignal


def _ctx(**kwargs) -> ObserveContext:
    base = dict(
        repo_root="/repo",
        git_dir="/repo/.git",
        common_dir="/repo/.git",
        preview_target=None,
    )
    base.update(kwargs)
    return ObserveContext(**base)


def test_head_file_maps_to_head():
    kinds, paths = classify_path_signal(
        PathSignal(path="/repo/.git/HEAD", mtime_ns=1),
        _ctx(),
    )
    assert ChangeKind.HEAD in kinds
    assert paths == frozenset()


def test_logs_head_maps_to_head():
    kinds, _ = classify_path_signal(
        PathSignal(path="/repo/.git/logs/HEAD", mtime_ns=1),
        _ctx(),
    )
    assert ChangeKind.HEAD in kinds


def test_index_maps_to_index():
    kinds, _ = classify_path_signal(
        PathSignal(path="/repo/.git/index", mtime_ns=1),
        _ctx(),
    )
    assert ChangeKind.INDEX in kinds


def test_refs_heads_maps_to_refs():
    kinds, _ = classify_path_signal(
        PathSignal(path="/repo/.git/refs/heads/main", mtime_ns=1),
        _ctx(),
    )
    assert ChangeKind.REFS in kinds


def test_refs_directory_maps_to_refs():
    """Directory discovery signals (new branch/tag) must classify as REFS."""
    kinds, _ = classify_path_signal(
        PathSignal(path="/repo/.git/refs/heads", mtime_ns=1),
        _ctx(),
    )
    assert ChangeKind.REFS in kinds


def test_stash_ref_maps_to_stash_and_refs():
    kinds, _ = classify_path_signal(
        PathSignal(path="/repo/.git/refs/stash", mtime_ns=1),
        _ctx(),
    )
    assert ChangeKind.STASH in kinds
    assert ChangeKind.REFS in kinds


def test_packed_refs_maps_to_refs():
    kinds, _ = classify_path_signal(
        PathSignal(path="/repo/.git/packed-refs", mtime_ns=1),
        _ctx(),
    )
    assert ChangeKind.REFS in kinds


def test_logs_refs_maps_to_refs():
    kinds, _ = classify_path_signal(
        PathSignal(path="/repo/.git/logs/refs/heads/main", mtime_ns=1),
        _ctx(),
    )
    assert ChangeKind.REFS in kinds


def test_worktree_file_maps_to_worktree_meta():
    kinds, paths = classify_path_signal(
        PathSignal(path="/repo/foo.py", mtime_ns=1),
        _ctx(),
    )
    assert ChangeKind.WORKTREE_META in kinds
    assert paths == frozenset({"foo.py"})


def test_preview_target_maps_to_preview_file():
    kinds, paths = classify_path_signal(
        PathSignal(path="/repo/foo.py", mtime_ns=1),
        _ctx(preview_target="foo.py"),
    )
    assert ChangeKind.PREVIEW_FILE in kinds
    assert ChangeKind.WORKTREE_META in kinds
    assert "foo.py" in paths


def test_common_dir_refs_when_separate_from_git_dir():
    kinds, _ = classify_path_signal(
        PathSignal(path="/common/refs/heads/feature", mtime_ns=1),
        _ctx(git_dir="/repo/.git", common_dir="/common"),
    )
    assert ChangeKind.REFS in kinds
