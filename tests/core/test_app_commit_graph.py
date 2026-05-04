# -*- coding: utf-8 -*-
"""Tests for the inline merge-graph layout algorithm."""

from pigit.app_commit_graph import compute_graph_rows
from pigit.git.model import Commit


def _mk(sha: str, parents: list[str]) -> Commit:
    return Commit(
        sha=sha,
        msg="",
        author="",
        unix_timestamp=0,
        status="pushed",
        extra_info="",
        tag=[],
        parents=parents,
    )


def test_empty():
    assert compute_graph_rows([]) == []


def test_linear_history():
    rows = compute_graph_rows(
        [_mk("c", ["b"]), _mk("b", ["a"]), _mk("a", [])]
    )
    assert len(rows) == 3

    assert rows[0].lanes_before == []
    assert rows[0].commit_lane == 0
    assert rows[0].closed_lanes == []
    assert rows[0].opened_lanes == []
    assert rows[0].lanes_after == ["b"]

    assert rows[1].lanes_before == ["b"]
    assert rows[1].commit_lane == 0
    assert rows[1].lanes_after == ["a"]

    assert rows[2].lanes_before == ["a"]
    assert rows[2].commit_lane == 0
    assert rows[2].lanes_after == []


def test_single_merge():
    # M is a merge of X (mainline) and Y (side branch tip pointing at X).
    rows = compute_graph_rows(
        [_mk("M", ["X", "Y"]), _mk("Y", ["X"]), _mk("X", [])]
    )

    assert rows[0].commit_lane == 0
    assert rows[0].closed_lanes == []
    assert rows[0].opened_lanes == [1]
    assert rows[0].lanes_after == ["X", "Y"]

    assert rows[1].lanes_before == ["X", "Y"]
    assert rows[1].commit_lane == 1
    assert rows[1].closed_lanes == []
    assert rows[1].lanes_after == ["X", "X"]

    assert rows[2].lanes_before == ["X", "X"]
    assert rows[2].commit_lane == 0
    assert rows[2].closed_lanes == [1]
    assert rows[2].opened_lanes == []
    assert rows[2].lanes_after == []


def test_nested_merges():
    # M1: parents [P1, M2]
    # M2: parents [P2, P3]
    # P1, P2, P3 linear back to a single root P1
    rows = compute_graph_rows(
        [
            _mk("M1", ["P1", "M2"]),
            _mk("M2", ["P2", "P3"]),
            _mk("P3", ["P2"]),
            _mk("P2", ["P1"]),
            _mk("P1", []),
        ]
    )

    assert rows[0].commit_lane == 0
    assert rows[0].opened_lanes == [1]
    assert rows[0].lanes_after == ["P1", "M2"]

    assert rows[1].commit_lane == 1
    assert rows[1].opened_lanes == [2]
    assert rows[1].lanes_after == ["P1", "P2", "P3"]

    assert rows[2].commit_lane == 2
    assert rows[2].closed_lanes == []
    assert rows[2].lanes_after == ["P1", "P2", "P2"]

    assert rows[3].commit_lane == 1
    assert rows[3].closed_lanes == [2]
    assert rows[3].lanes_after == ["P1", "P1"]

    assert rows[4].commit_lane == 0
    assert rows[4].closed_lanes == [1]
    assert rows[4].lanes_after == []


def test_octopus_merge():
    rows = compute_graph_rows(
        [
            _mk("M", ["P1", "P2", "P3"]),
            _mk("P1", ["R"]),
            _mk("P2", ["R"]),
            _mk("P3", ["R"]),
            _mk("R", []),
        ]
    )

    assert rows[0].commit_lane == 0
    assert rows[0].opened_lanes == [1, 2]
    assert rows[0].lanes_after == ["P1", "P2", "P3"]

    assert rows[-1].commit_lane == 0
    assert rows[-1].closed_lanes == [1, 2]
    assert rows[-1].lanes_after == []


def test_parent_outside_window():
    # 'a' is the parent of 'b' but is not in the loaded slice.
    # The lane should stay open (not error).
    rows = compute_graph_rows([_mk("c", ["b"]), _mk("b", ["a"])])
    assert rows[-1].lanes_after == ["a"]


def test_opened_lane_skips_closed_slot():
    # If a lane closes on this row and a new parent needs a slot, the new
    # opened lane must NOT reuse the just-closed slot — it should pick a
    # fresh column to keep the rendering clean.
    #
    # Scenario: lanes = [X, X] (two lanes both waiting for X). Commit X has
    # parents [A, B]. lane 0 continues with A, lane 1 closes. Parent B needs
    # a new lane — should be lane 2, not lane 1.
    commits = [
        _mk("M1", ["X", "X"]),
        _mk("X", ["A", "B"]),
    ]
    # Hand-craft: at row 0 we open lane 1 with X; both lanes wait for X.
    # Row 1 collapses both into lane 0 (commit_lane=0, closed=[1]),
    # then opens parent B in a new lane.
    rows = compute_graph_rows(commits)
    assert rows[1].commit_lane == 0
    assert rows[1].closed_lanes == [1]
    assert rows[1].opened_lanes  # at least one new lane
    assert 1 not in rows[1].opened_lanes


def test_orphan_branch_allocates_new_lane():
    # Two commits with no parent/child relationship to each other.
    # Each gets its own lane.
    rows = compute_graph_rows([_mk("a", []), _mk("b", [])])
    assert rows[0].commit_lane == 0
    assert rows[0].lanes_after == []
    # 'b' has no incoming, so it allocates lane 0 again.
    assert rows[1].commit_lane == 0
