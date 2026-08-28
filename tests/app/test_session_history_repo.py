# -*- coding: utf-8 -*-
"""
Module: tests/app/test_session_history_repo.py
Description: SessionHistory repo-path isolation for multi-repo undo.
Author: Zev
Date: 2026-08-28
"""

from __future__ import annotations

from unittest.mock import Mock

from pigit.session_history import HistoryRecord, ReverseCommand, SessionHistory


def _record(desc: str, repo: str) -> HistoryRecord:
    return HistoryRecord(
        description=desc,
        commands=[
            ReverseCommand(op_type="stage", payload={"path": "f"}),
        ],
        timestamp=0.0,
        panel_hint="status",
        repo_path=repo,
    )


def test_push_stamps_active_repo_when_blank():
    history = SessionHistory()
    history.attach_repo("/a")
    history.push(
        HistoryRecord(
            description="x",
            commands=[],
            timestamp=0.0,
            panel_hint="status",
        )
    )
    assert history.peek(1)[0].repo_path == "/a"


def test_peek_filters_to_active_repo():
    history = SessionHistory()
    history.attach_repo("/a")
    history.push(_record("a1", "/a"))
    history.push(_record("b1", "/b"))
    history.push(_record("a2", "/a"))
    assert [r.description for r in history.peek(10)] == ["a2", "a1"]
    history.attach_repo("/b")
    assert [r.description for r in history.peek(10)] == ["b1"]


def test_reverse_skips_foreign_top_and_undoes_active():
    history = SessionHistory()
    history.attach_repo("/a")
    history.push(_record("a1", "/a"))
    history.push(_record("b1", "/b"))
    git = Mock()
    git.add_file = Mock()
    result = history.reverse(git)
    assert result.success
    assert "a1" in result.message
    git.add_file.assert_called_once_with("f")
    history.attach_repo("/b")
    assert [r.description for r in history.peek(10)] == ["b1"]


def test_reverse_foreign_only_stack_messages():
    history = SessionHistory()
    history.attach_repo("/a")
    history.push(_record("b1", "/b"))
    result = history.reverse(Mock())
    assert not result.success
    assert "another repository" in result.message


def test_reverse_to_only_active_repo_indices():
    history = SessionHistory()
    history.attach_repo("/a")
    history.push(_record("a1", "/a"))
    history.push(_record("b1", "/b"))
    history.push(_record("a2", "/a"))
    git = Mock()
    git.add_file = Mock(return_value=None)

    def _ok(_path):
        return None

    git.add_file.side_effect = _ok
    # Monkeypatch ReverseCommand via execute path: stage dispatcher calls add_file
    result = history.reverse_to(0, git)  # newest active only (a2)
    assert result.success
    assert history.peek(10)[0].description == "a1"
