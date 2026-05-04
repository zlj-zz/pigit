# -*- coding: utf-8 -*-
"""
Module: pigit/app_commit_graph.py
Description: Pure algorithm for inline merge-graph layout per commit row.
Author: Zev
Date: 2026-05-04
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence, TYPE_CHECKING

if TYPE_CHECKING:
    from pigit.git.model import Commit


@dataclass
class GraphRow:
    """Lane layout for one commit row.

    Lanes are not compacted between rows; once a column is allocated it stays
    until that lane closes, at which point the column may be reused later.

    `closed_lanes` / `opened_lanes` are always > `commit_lane` by construction,
    so the renderer can use a single direction of curve glyphs.
    """

    lanes_before: list[Optional[str]]
    commit_lane: int
    closed_lanes: list[int]
    opened_lanes: list[int]
    lanes_after: list[Optional[str]]


def compute_graph_rows(commits: Sequence["Commit"]) -> list[GraphRow]:
    """Compute graph layout for ``commits`` (newest-first, as ``git log`` emits).

    For each commit:

    1. Find lanes whose expected SHA matches the commit (``incoming``).
       The smallest is the commit's own lane; the rest close on this row.
    2. Replace the commit lane with the commit's first parent (or clear it).
    3. For each additional parent (merge), open a new lane to the right of
       ``commit_lane``.
    4. Trim trailing ``None`` slots so column count tracks the active set.
    """
    lanes: list[Optional[str]] = []
    rows: list[GraphRow] = []

    for commit in commits:
        sha = commit.sha
        parents = list(commit.parents)

        lanes_before = list(lanes)

        incoming = [i for i, s in enumerate(lanes) if s == sha]
        if incoming:
            commit_lane = min(incoming)
            closed_lanes = sorted(set(incoming) - {commit_lane})
        else:
            commit_lane = _alloc_lane(lanes, prefer_after=0)
            closed_lanes = []

        lanes[commit_lane] = parents[0] if parents else None
        excluded: set[int] = set()
        for i in closed_lanes:
            lanes[i] = None
            excluded.add(i)

        opened_lanes: list[int] = []
        for parent_sha in parents[1:]:
            slot = _alloc_lane(
                lanes,
                prefer_after=commit_lane + 1,
                exclude=excluded,
            )
            lanes[slot] = parent_sha
            opened_lanes.append(slot)
            excluded.add(slot)

        while lanes and lanes[-1] is None:
            lanes.pop()

        rows.append(
            GraphRow(
                lanes_before=lanes_before,
                commit_lane=commit_lane,
                closed_lanes=closed_lanes,
                opened_lanes=opened_lanes,
                lanes_after=list(lanes),
            )
        )

    return rows


def _alloc_lane(
    lanes: list[Optional[str]],
    *,
    prefer_after: int = 0,
    exclude: Optional[set[int]] = None,
) -> int:
    """First ``None`` slot at index ``>= prefer_after`` and not in ``exclude``;
    append a new lane otherwise."""
    excl = exclude or set()
    for i in range(prefer_after, len(lanes)):
        if lanes[i] is None and i not in excl:
            return i
    lanes.append(None)
    return len(lanes) - 1
