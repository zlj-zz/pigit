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
_GIT_DIR_FILES = ("HEAD", "index", "logs/HEAD", "FETCH_HEAD")

# Files always watched under the common dir when present.
_COMMON_DIR_FILES = ("packed-refs",)

# Directories whose mtime reveals newly created refs (not present at expand).
_GIT_DISCOVERY_DIRS = (
    "refs",
    "refs/heads",
    "refs/tags",
    "refs/remotes",
    "logs",
    "logs/refs",
)

# Tip files walked into the steady-state poll set (not remotes — those use
# FETCH_HEAD + discovery dirs; parent dir mtime does not track tip edits).
_GIT_TIP_WALK_DIRS = (
    "refs/heads",
    "refs/tags",
    "logs/refs/heads",
    "logs/refs/tags",
)

# Single-file refs that are not under heads/tags but still need tip tracking.
_GIT_TIP_FILES = ("refs/stash", "logs/refs/stash")

# Cap on worktree / dirty-file paths polled per Status-focused attach.
MAX_WORKTREE_STAT_PATHS = 400

_META_KINDS = frozenset({"git_dir", "common_dir"})
_WORKTREE_KINDS = frozenset({"worktree", "file"})


def build_git_metadata_paths(git_dir: str, common_dir: str) -> list[str]:
    """Return absolute paths to git metadata files/dirs that should be polled.

    Steady-state tip files are limited to local heads/tags (plus stash when
    present). Remote-tracking tips are not enumerated; ``FETCH_HEAD``,
    ``packed-refs``, and ``refs/remotes`` directory mtime cover fetch/discovery.

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

    for rel in _GIT_DISCOVERY_DIRS:
        path = common / rel
        if path.is_dir():
            found.append(str(path.resolve()))

    for rel in _GIT_TIP_WALK_DIRS:
        found.extend(_walk_files(common / rel))

    for rel in _GIT_TIP_FILES:
        path = common / rel
        if path.is_file():
            found.append(str(path.resolve()))

    return list(dict.fromkeys(found))


def build_worktree_observe_paths(
    repo_root: str,
    status_rel_paths: Sequence[str] = (),
    *,
    max_paths: int = MAX_WORKTREE_STAT_PATHS,
) -> tuple[list[str], bool]:
    """Build worktree paths: nested dirs, top-level files, status files.

    Nested directories are polled so a deep create (e.g. ``src/deep/new.py``)
    bumps a watched mtime. Top-level files catch content edits without a
    prior status row. Denied names are skipped. Status-relative paths that
    are not denied are added so dirty-file content edits are visible.

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
        found.extend(_walk_worktree_dirs(root, max_paths=max_paths))
        try:
            children = sorted(root.iterdir(), key=lambda p: p.name)
        except OSError:
            children = []
        for child in children:
            if is_denied_name(child.name) or child.is_dir():
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


def expand_metadata_paths(roots: Sequence[WatchRoot]) -> list[str]:
    """Expand git_dir / common_dir roots into metadata poll paths."""
    git_dir: str | None = None
    common_dir: str | None = None
    for root in roots:
        if root.kind == "git_dir":
            git_dir = str(Path(root.path).resolve())
        elif root.kind == "common_dir":
            common_dir = str(Path(root.path).resolve())
    if git_dir is None:
        return []
    return build_git_metadata_paths(git_dir, common_dir or git_dir)


def expand_worktree_paths(roots: Sequence[WatchRoot]) -> tuple[list[str], bool]:
    """Expand worktree / file roots into worktree poll paths."""
    status_files: list[str] = []
    worktree_root: str | None = None
    for root in roots:
        abs_path = str(Path(root.path).resolve())
        if root.kind == "file":
            status_files.append(abs_path)
        elif root.kind == "worktree":
            worktree_root = abs_path

    if worktree_root is None:
        extra = [p for p in status_files if Path(p).exists()]
        if len(extra) > MAX_WORKTREE_STAT_PATHS:
            return extra[:MAX_WORKTREE_STAT_PATHS], True
        return extra, False

    root_path = Path(worktree_root)
    status_rels: list[str] = []
    extras: list[str] = []
    for abs_file in status_files:
        try:
            rel = Path(abs_file).resolve().relative_to(root_path).as_posix()
        except ValueError:
            extras.append(abs_file)
            continue
        status_rels.append(rel)
    built, truncated = build_worktree_observe_paths(
        worktree_root,
        status_rel_paths=status_rels,
    )
    return list(dict.fromkeys([*built, *extras])), truncated


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
    meta = expand_metadata_paths(roots)
    worktree, truncated = expand_worktree_paths(roots)
    return list(dict.fromkeys([*meta, *worktree])), truncated


def roots_signature(roots: Sequence[WatchRoot]) -> frozenset[tuple[str, str]]:
    """Stable identity of a roots list for no-op update detection."""
    return frozenset(
        (root.kind, str(Path(root.path).resolve())) for root in roots
    )


def metadata_roots_signature(
    roots: Sequence[WatchRoot],
) -> frozenset[tuple[str, str]]:
    """Identity of git_dir / common_dir roots only."""
    return frozenset(
        (root.kind, str(Path(root.path).resolve()))
        for root in roots
        if root.kind in _META_KINDS
    )


def worktree_roots_signature(
    roots: Sequence[WatchRoot],
) -> frozenset[tuple[str, str]]:
    """Identity of worktree / file roots only."""
    return frozenset(
        (root.kind, str(Path(root.path).resolve()))
        for root in roots
        if root.kind in _WORKTREE_KINDS
    )


def _walk_files(root: Path) -> list[str]:
    """Return all regular files under ``root``, or empty if missing."""
    if not root.is_dir():
        return []
    out: list[str] = []
    for path in root.rglob("*"):
        if path.is_file():
            out.append(str(path.resolve()))
    return out


def _walk_worktree_dirs(root: Path, *, max_paths: int) -> list[str]:
    """BFS directory paths under ``root``, skipping denied names."""
    out: list[str] = []
    queue: list[Path] = [root]
    while queue and len(out) < max_paths:
        current = queue.pop(0)
        try:
            children = sorted(current.iterdir(), key=lambda p: p.name)
        except OSError:
            continue
        for child in children:
            if not child.is_dir() or is_denied_name(child.name):
                continue
            try:
                resolved = str(child.resolve())
            except OSError:
                continue
            out.append(resolved)
            if len(out) >= max_paths:
                break
            queue.append(child)
    return out
