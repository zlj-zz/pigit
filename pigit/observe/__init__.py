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
from .paths import build_git_metadata_paths
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
    "StatMtimeBackend",
    "SystemClock",
    "WatchRoot",
    "build_git_metadata_paths",
    "classify_path_signal",
]
