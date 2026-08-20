# -*- coding: utf-8 -*-
"""
Module: pigit/observe/types.py
Description: Shared types for repo filesystem observation.
Author: Zev
Date: 2026-08-20
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Literal


class ChangeKind(Enum):
    """Semantic change categories derived from path signals."""

    HEAD = "head"
    REFS = "refs"
    INDEX = "index"
    STASH = "stash"
    WORKTREE_META = "worktree_meta"
    PREVIEW_FILE = "preview_file"


class BackendHealth(Enum):
    """Observation backend health."""

    OK = "ok"
    DEGRADED = "degraded"
    FAILED = "failed"


@dataclass(frozen=True)
class PathSignal:
    """One filesystem observation. ``path`` is absolute at the backend boundary."""

    path: str
    mtime_ns: int | None = None


@dataclass(frozen=True)
class WatchRoot:
    """A rooted tree or file the backend should observe."""

    kind: Literal["git_dir", "common_dir", "worktree", "file"]
    path: str


@dataclass(frozen=True)
class ChangeBatch:
    """Debounced set of change kinds and optional repo-relative paths."""

    kinds: frozenset[ChangeKind]
    paths: frozenset[str]


@dataclass(frozen=True)
class ObserveContext:
    """Paths needed to classify a signal (all directory paths absolute)."""

    repo_root: str
    git_dir: str
    common_dir: str
    preview_target: str | None = None
