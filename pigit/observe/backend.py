# -*- coding: utf-8 -*-
"""
Module: pigit/observe/backend.py
Description: ObservationBackend protocol, StatMtimeBackend, and FakeBackend.
Author: Zev
Date: 2026-08-20
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, Sequence

from .paths import (
    expand_metadata_paths,
    expand_worktree_paths,
    metadata_roots_signature,
    roots_signature,
    worktree_roots_signature,
)
from .types import BackendHealth, PathSignal, WatchRoot


class ObservationBackend(Protocol):
    """Filesystem observation source.

    Phase A backends are pull-based: call ``poll()`` from the UI/observer.
    A later push backend (e.g. optional watchdog) may enqueue onto a shared
    ``queue.Queue`` from a helper thread and return ``[]`` from ``poll()``.
    """

    def start(self, roots: Sequence[WatchRoot]) -> None:
        """Begin observing ``roots`` (may replace prior roots)."""
        ...

    def stop(self) -> None:
        """Stop observation and release resources."""
        ...

    def health(self) -> BackendHealth:
        """Return current backend health."""
        ...

    def poll(self) -> list[PathSignal]:
        """Return new signals since the previous poll (may be empty)."""
        ...


class StatMtimeBackend:
    """Poll selected paths and emit signals when ``st_mtime_ns`` changes."""

    def __init__(self, paths: Sequence[str] | None = None) -> None:
        self._explicit_paths = [str(Path(p).resolve()) for p in (paths or ())]
        self._meta_paths: list[str] = []
        self._worktree_paths: list[str] = []
        self._paths: list[str] = list(self._explicit_paths)
        self._last_mtime: dict[str, int | None] = {}
        self._meta_dir_paths: set[str] = set()
        self._roots: list[WatchRoot] = []
        self._roots_sig: frozenset[tuple[str, str]] = frozenset()
        self._meta_sig: frozenset[tuple[str, str]] = frozenset()
        self._worktree_sig: frozenset[tuple[str, str]] = frozenset()
        self._started = False
        self._health = BackendHealth.OK

    def start(self, roots: Sequence[WatchRoot]) -> None:
        """Reset baseline mtimes for explicit paths plus paths from ``roots``."""
        self._roots = list(roots)
        self._roots_sig = roots_signature(roots)
        self._meta_sig = metadata_roots_signature(roots)
        self._worktree_sig = worktree_roots_signature(roots)
        self._meta_paths = expand_metadata_paths(roots)
        self._worktree_paths, truncated = expand_worktree_paths(roots)
        self._apply_merged_paths(reset_baseline=True, truncated=truncated)
        self._started = True

    def update_roots(self, roots: Sequence[WatchRoot]) -> None:
        """Update observed paths, keeping baselines for paths that remain.

        No-op when the root set is unchanged. Status file list changes only
        rebuild the worktree half; git metadata is left alone.
        """
        if not self._started:
            self.start(roots)
            return
        new_sig = roots_signature(roots)
        if new_sig == self._roots_sig:
            return
        new_meta_sig = metadata_roots_signature(roots)
        new_wt_sig = worktree_roots_signature(roots)
        self._roots = list(roots)
        self._roots_sig = new_sig
        truncated = False
        if new_meta_sig != self._meta_sig:
            self._meta_sig = new_meta_sig
            self._meta_paths = expand_metadata_paths(roots)
        if new_wt_sig != self._worktree_sig:
            self._worktree_sig = new_wt_sig
            self._worktree_paths, truncated = expand_worktree_paths(roots)
        self._apply_merged_paths(reset_baseline=False, truncated=truncated)

    def stop(self) -> None:
        """Clear path state."""
        self._started = False
        self._paths = []
        self._meta_paths = []
        self._worktree_paths = []
        self._last_mtime.clear()
        self._meta_dir_paths.clear()
        self._roots = []
        self._roots_sig = frozenset()
        self._meta_sig = frozenset()
        self._worktree_sig = frozenset()

    def health(self) -> BackendHealth:
        """Return backend health."""
        return self._health

    def poll(self) -> list[PathSignal]:
        """Emit a signal for each path whose mtime changed since last poll."""
        if not self._started:
            return []
        out: list[PathSignal] = []
        for path in self._paths:
            current = _read_mtime_ns(path)
            previous = self._last_mtime.get(path)
            if previous is None:
                self._last_mtime[path] = current
                continue
            if current != previous:
                self._last_mtime[path] = current
                out.append(PathSignal(path=path, mtime_ns=current))
        if out and self._roots and any(s.path in self._meta_dir_paths for s in out):
            # New local tips under discovery dirs enter the poll set.
            self._meta_paths = expand_metadata_paths(self._roots)
            self._apply_merged_paths(reset_baseline=False, truncated=False)
        return out

    def _apply_merged_paths(self, *, reset_baseline: bool, truncated: bool) -> None:
        """Merge explicit + metadata + worktree paths and update baselines."""
        merged = list(
            dict.fromkeys(
                [*self._explicit_paths, *self._meta_paths, *self._worktree_paths]
            )
        )
        self._health = BackendHealth.DEGRADED if truncated else BackendHealth.OK
        self._meta_dir_paths = {p for p in self._meta_paths if Path(p).is_dir()}
        if reset_baseline:
            self._paths = merged
            self._last_mtime = {p: _read_mtime_ns(p) for p in self._paths}
            return
        new_mtime: dict[str, int | None] = {}
        for path in merged:
            if path in self._last_mtime:
                new_mtime[path] = self._last_mtime[path]
            else:
                new_mtime[path] = _read_mtime_ns(path)
        self._paths = merged
        self._last_mtime = new_mtime


class FakeBackend:
    """Test backend that returns a scripted list of signals on each poll."""

    def __init__(self, scripted: Sequence[Sequence[PathSignal]] | None = None) -> None:
        self._scripted = [list(batch) for batch in (scripted or ())]
        self._index = 0
        self._started = False
        self._health = BackendHealth.OK

    def start(self, roots: Sequence[WatchRoot]) -> None:
        """Mark started; roots ignored."""
        self._started = True

    def stop(self) -> None:
        """Mark stopped."""
        self._started = False

    def health(self) -> BackendHealth:
        """Return configured health."""
        return self._health

    def set_health(self, health: BackendHealth) -> None:
        """Test helper to force health."""
        self._health = health

    def poll(self) -> list[PathSignal]:
        """Return the next scripted batch, or empty when exhausted."""
        if not self._started or self._index >= len(self._scripted):
            return []
        batch = self._scripted[self._index]
        self._index += 1
        return list(batch)


def _read_mtime_ns(path: str) -> int | None:
    """Return ``st_mtime_ns`` or ``None`` if the path is missing."""
    try:
        return Path(path).stat().st_mtime_ns
    except OSError:
        return None
