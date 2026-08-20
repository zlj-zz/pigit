# -*- coding: utf-8 -*-
"""
Package: pigit.observe
Description: Repo filesystem observation (backends, classify, coordinate).
Author: Zev
Date: 2026-08-20
"""

from __future__ import annotations

from .backend import FakeBackend, StatMtimeBackend
from .classify import classify_path_signal
from .clock import FakeClock, SystemClock
from .coordinator import RefreshCoordinator
from .digest import hash_porcelain
from .observer import RepoObserver
from .overlay import should_defer_repo_refresh
from .paths import build_git_metadata_paths, build_worktree_observe_paths
from .types import (
    BackendHealth,
    ChangeBatch,
    ChangeKind,
    ObserveContext,
    PathSignal,
    WatchRoot,
)

__all__ = [
    "BackendHealth",
    "ChangeBatch",
    "ChangeKind",
    "FakeBackend",
    "FakeClock",
    "ObserveContext",
    "PathSignal",
    "RefreshCoordinator",
    "RepoObserver",
    "StatMtimeBackend",
    "SystemClock",
    "WatchRoot",
    "build_git_metadata_paths",
    "build_worktree_observe_paths",
    "classify_path_signal",
    "hash_porcelain",
    "should_defer_repo_refresh",
]
