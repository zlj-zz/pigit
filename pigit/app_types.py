"""
Module: pigit/app_types.py
Description: Shared TUI data types used by both ViewModels and panels.
Author: Zev
Date: 2026-06-04
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .git.model import Branch, Commit, File


@dataclass
class FileInfo:
    file: File
    size: str
    mtime: str


@dataclass
class BranchInfo:
    branch: Branch
    recent_msg: str
    recent_author: str
    created: str


@dataclass
class CommitInfo:
    commit: Commit
    changed_files: list[tuple[str, int, int]]
    total_add: int
    total_del: int


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


InspectorData = FileInfo | BranchInfo | CommitInfo | None
