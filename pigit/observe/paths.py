# -*- coding: utf-8 -*-
"""
Module: pigit/observe/paths.py
Description: Build git metadata and worktree path lists for StatMtime.
Author: Zev
Date: 2026-08-20
"""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

from .denylist import is_denied_name, rel_path_is_denied
from .types import WatchRoot

# Filenames always watched under the per-worktree git dir when present.
_GIT_DIR_FILES = ("HEAD", "index", "logs/HEAD")

# Files always watched under the common dir when present.
_COMMON_DIR_FILES = ("packed-refs",)

# Cap on worktree / dirty-file paths polled per Status-focused attach.
MAX_WORKTREE_STAT_PATHS = 400


def build_git_metadata_paths(git_dir: str, common_dir: str) -> list[str]:
    """Return absolute paths to git metadata files that should be polled.

    Under ``common_dir``: ``packed-refs``, files under ``refs/`` and
    ``logs/refs/``. Under ``git_dir``: ``HEAD``, ``index``, ``logs/HEAD``.
    Missing paths are skipped. ``objects/`` is never included.

    Args:
        git_dir: Absolute per-worktree git directory.
        common_dir: Absolute common git directory (may equal ``git_dir``).

    Returns:
        Deduplicated list of absolute path strings.
    """
    git = Path(git_dir).resolve()
    common = Path(common_dir).resolve()
    found: list[str] = []

    for rel in _GIT_DIR_FILES:
        path = git / rel
        if path.is_file():
            found.append(str(path.resolve()))

    for rel in _COMMON_DIR_FILES:
        path = common / rel
        if path.is_file():
            found.append(str(path.resolve()))

    found.extend(_walk_files(common / "refs"))
    found.extend(_walk_files(common / "logs" / "refs"))

    # Deduplicate while preserving order.
    return list(dict.fromkeys(found))


def build_worktree_observe_paths(
    repo_root: str,
    status_rel_paths: Sequence[str] = (),
    *,
    max_paths: int = MAX_WORKTREE_STAT_PATHS,
) -> tuple[list[str], bool]:
    """Build worktree paths: top-level entries plus known status files.

    Top-level files and directories are included (directory mtime catches
    add/remove). Denied names are skipped. Status-relative paths that are
    not denied are added so content edits are visible to StatMtime.

    Args:
        repo_root: Absolute repository working tree.
        status_rel_paths: Repo-relative paths from the last status load.
        max_paths: Soft budget; excess paths are dropped.

    Returns:
        ``(paths, truncated)`` where ``truncated`` is True if the budget cut
        paths.
    """
    root = Path(repo_root).resolve()
    found: list[str] = []

    if root.is_dir():
        try:
            children = sorted(root.iterdir(), key=lambda p: p.name)
        except OSError:
            children = []
        for child in children:
            if is_denied_name(child.name):
                continue
            try:
                found.append(str(child.resolve()))
            except OSError:
                continue

    for rel in status_rel_paths:
        if not rel or rel_path_is_denied(rel):
            continue
        path = root / rel
        try:
            if path.exists():
                found.append(str(path.resolve()))
        except OSError:
            continue

    deduped = list(dict.fromkeys(found))
    if len(deduped) > max_paths:
        return deduped[:max_paths], True
    return deduped, False


def expand_watch_roots_to_paths(
    roots: Sequence[WatchRoot],
) -> tuple[list[str], bool]:
    """Expand watch roots into concrete file/dir paths for StatMtime.

    Args:
        roots: Declared observation roots.

    Returns:
        ``(paths, truncated)`` — absolute paths to poll (git metadata first),
        and whether the worktree budget dropped paths.
    """
    meta: list[str] = []
    worktree_extra: list[str] = []
    git_dir: str | None = None
    common_dir: str | None = None
    status_files: list[str] = []
    worktree_root: str | None = None
    truncated = False

    for root in roots:
        abs_path = str(Path(root.path).resolve())
        if root.kind == "git_dir":
            git_dir = abs_path
        elif root.kind == "common_dir":
            common_dir = abs_path
        elif root.kind == "file":
            status_files.append(abs_path)
        elif root.kind == "worktree":
            worktree_root = abs_path

    if git_dir is not None:
        common = common_dir or git_dir
        meta.extend(build_git_metadata_paths(git_dir, common))

    if worktree_root is not None:
        root_path = Path(worktree_root)
        status_rels: list[str] = []
        for abs_file in status_files:
            try:
                rel = Path(abs_file).resolve().relative_to(root_path).as_posix()
            except ValueError:
                worktree_extra.append(abs_file)
                continue
            status_rels.append(rel)
        built, wt_truncated = build_worktree_observe_paths(
            worktree_root,
            status_rel_paths=status_rels,
        )
        truncated = truncated or wt_truncated
        worktree_extra.extend(built)
    else:
        for abs_file in status_files:
            if Path(abs_file).exists():
                worktree_extra.append(abs_file)
        if len(worktree_extra) > MAX_WORKTREE_STAT_PATHS:
            worktree_extra = worktree_extra[:MAX_WORKTREE_STAT_PATHS]
            truncated = True

    return list(dict.fromkeys([*meta, *worktree_extra])), truncated


def _walk_files(root: Path) -> list[str]:
    """Return all regular files under ``root``, or empty if missing."""
    if not root.is_dir():
        return []
    out: list[str] = []
    for path in root.rglob("*"):
        if path.is_file():
            out.append(str(path.resolve()))
    return out
