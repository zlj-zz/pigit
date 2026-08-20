# -*- coding: utf-8 -*-
"""
Module: pigit/observe/classify.py
Description: Pure PathSignal → ChangeKind classification.
Author: Zev
Date: 2026-08-20
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath

from .types import ChangeKind, ObserveContext, PathSignal


def classify_path_signal(
    signal: PathSignal,
    ctx: ObserveContext,
) -> tuple[frozenset[ChangeKind], frozenset[str]]:
    """Map a filesystem signal to change kinds and repo-relative paths.

    Args:
        signal: Absolute path observation from a backend.
        ctx: Repo layout and optional Status preview target.

    Returns:
        Tuple of (kinds, repo-relative paths). Paths may be empty.
    """
    abs_path = Path(signal.path).resolve()
    git_dir = Path(ctx.git_dir).resolve()
    common_dir = Path(ctx.common_dir).resolve()
    repo_root = Path(ctx.repo_root).resolve()

    kinds: set[ChangeKind] = set()
    rel_paths: set[str] = set()

    if _is_under(abs_path, git_dir) or _is_under(abs_path, common_dir):
        kinds |= _classify_git_meta(abs_path, git_dir, common_dir)
    elif _is_under(abs_path, repo_root):
        rel = _repo_relative(abs_path, repo_root)
        if rel is not None:
            rel_paths.add(rel)
            kinds.add(ChangeKind.WORKTREE_META)
            if ctx.preview_target is not None and rel == ctx.preview_target:
                kinds.add(ChangeKind.PREVIEW_FILE)

    return frozenset(kinds), frozenset(rel_paths)


def _is_under(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _repo_relative(path: Path, repo_root: Path) -> str | None:
    try:
        return path.relative_to(repo_root).as_posix()
    except ValueError:
        return None


def _classify_git_meta(
    abs_path: Path,
    git_dir: Path,
    common_dir: Path,
) -> set[ChangeKind]:
    """Classify a path under git_dir or common_dir."""
    kinds: set[ChangeKind] = set()
    for root in {git_dir, common_dir}:
        if not _is_under(abs_path, root):
            continue
        rel = abs_path.relative_to(root).as_posix()
        kinds |= _kinds_for_git_rel(rel)
    return kinds


def _kinds_for_git_rel(rel: str) -> set[ChangeKind]:
    """Classify a path relative to a git or common dir."""
    kinds: set[ChangeKind] = set()
    posix = PurePosixPath(rel)
    parts = posix.parts

    if rel == "HEAD" or rel == "logs/HEAD":
        kinds.add(ChangeKind.HEAD)
        return kinds

    if rel == "index":
        kinds.add(ChangeKind.INDEX)
        return kinds

    if rel == "packed-refs":
        kinds.add(ChangeKind.REFS)
        return kinds

    if parts and parts[0] == "refs":
        kinds.add(ChangeKind.REFS)
        if len(parts) >= 2 and parts[1] == "stash":
            kinds.add(ChangeKind.STASH)
        return kinds

    if len(parts) >= 2 and parts[0] == "logs" and parts[1] == "refs":
        kinds.add(ChangeKind.REFS)
        if len(parts) >= 3 and parts[2] == "stash":
            kinds.add(ChangeKind.STASH)
        return kinds

    return kinds
