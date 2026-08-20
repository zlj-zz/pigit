# -*- coding: utf-8 -*-
"""
Module: pigit/observe/paths.py
Description: Build git metadata path lists for StatMtime observation.
Author: Zev
Date: 2026-08-20
"""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

from .types import WatchRoot

# Filenames always watched under the per-worktree git dir when present.
_GIT_DIR_FILES = ("HEAD", "index", "logs/HEAD")

# Files always watched under the common dir when present.
_COMMON_DIR_FILES = ("packed-refs",)


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


def expand_watch_roots_to_paths(roots: Sequence[WatchRoot]) -> list[str]:
    """Expand watch roots into concrete file paths for StatMtime.

    Args:
        roots: Declared observation roots.

    Returns:
        Absolute file paths to poll.
    """
    paths: list[str] = []
    git_dir: str | None = None
    common_dir: str | None = None

    for root in roots:
        abs_path = str(Path(root.path).resolve())
        if root.kind == "git_dir":
            git_dir = abs_path
        elif root.kind == "common_dir":
            common_dir = abs_path
        elif root.kind == "file":
            if Path(abs_path).is_file():
                paths.append(abs_path)
        elif root.kind == "worktree":
            # Phase 5 expands worktree; Phase 1 ignores.
            continue

    if git_dir is not None:
        common = common_dir or git_dir
        paths.extend(build_git_metadata_paths(git_dir, common))

    return list(dict.fromkeys(paths))


def _walk_files(root: Path) -> list[str]:
    """Return all regular files under ``root``, or empty if missing."""
    if not root.is_dir():
        return []
    out: list[str] = []
    for path in root.rglob("*"):
        if path.is_file():
            out.append(str(path.resolve()))
    return out
