"""
Module: pigit/app_types.py
Description: Shared TUI data types used by ViewModels and panels.
Author: Zev
Date: 2026-06-04
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol, runtime_checkable


def guard_or_identity(
    guard: Callable[[Callable[[list[str]], None]], Callable[[list[str]], None]]
    | None,
    callback: Callable[[list[str]], None],
) -> Callable[[list[str]], None]:
    """Apply an async ``guard`` (repo token) when injected, else pass through."""
    if guard is None:
        return callback
    return guard(callback)


@dataclass
class FileSnapshot:
    identity: str
    path: str
    blobs: str
    stages: str | None
    size: str
    mode: str
    last: str | None


@dataclass
class BranchSnapshot:
    identity: str
    tip: str
    created: str | None
    # None means ancestry could not be determined (stale/deleted ref).
    contained: bool | None
    current: str
    upstream: str
    ahead: str
    behind: str
    recent_msg: str
    recent_author: str


@dataclass
class CommitSnapshot:
    identity: str
    sha: str
    msg: str
    author: str
    when: str
    status: str
    tags: str
    parents: list[str]
    files: list[tuple[str, int, int]]
    total_add: int
    total_del: int


@dataclass
class StashSnapshot:
    identity: str
    author: str | None
    when: str | None
    parents: list[str]
    files: list[tuple[str, int, int]]
    total_add: int
    total_del: int


InspectorSnapshot = FileSnapshot | BranchSnapshot | CommitSnapshot | StashSnapshot


@runtime_checkable
class InspectorHost(Protocol):
    def get_inspector_snapshot(self) -> InspectorSnapshot | None:
        """Return a frozen snapshot, or None when there is no selection."""
        ...


@dataclass
class GraphRow:
    """Lane layout for one commit row.

    Lanes are not compacted between rows; once a column is allocated it stays
    until that lane closes, at which point the column may be reused later.

    `closed_lanes` / `opened_lanes` are always > `commit_lane` by construction,
    so the renderer can use a single direction of curve glyphs.
    """

    lanes_before: list[str | None]
    commit_lane: int
    closed_lanes: list[int]
    opened_lanes: list[int]
    lanes_after: list[str | None]
