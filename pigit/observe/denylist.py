# -*- coding: utf-8 -*-
"""
Module: pigit/observe/denylist.py
Description: Default name denylist for worktree observation paths.
Author: Zev
Date: 2026-08-20
"""

from __future__ import annotations

from pathlib import PurePosixPath

DEFAULT_WORKTREE_DENY_NAMES = frozenset(
    {
        ".git",
        "node_modules",
        ".venv",
        "venv",
        "dist",
        "build",
        "__pycache__",
        ".tox",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".idea",
        ".vscode",
        "target",
        "vendor",
        ".eggs",
    }
)


def is_denied_name(name: str) -> bool:
    """Return True when a single path segment should not be observed."""
    if name in DEFAULT_WORKTREE_DENY_NAMES:
        return True
    # Match egg-info dirs without glob dependency.
    if name.endswith(".egg-info"):
        return True
    return False


def rel_path_is_denied(rel_posix: str) -> bool:
    """Return True when any segment of a repo-relative path is denied."""
    for part in PurePosixPath(rel_posix).parts:
        if is_denied_name(part):
            return True
    return False
