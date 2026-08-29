# -*- coding: utf-8 -*-
"""
Module: tests/app/test_session_history_rewind.py
Description: rewind op, describe rendering, and push_rewind for undo extension.
Author: Zev
Date: 2026-08-29
"""

from __future__ import annotations

from unittest.mock import Mock

from pigit.session_history import (
    HistoryRecord,
    ReverseCommand,
    SessionHistory,
    push_rewind,
)


def _git(*, dirty: bool = False) -> Mock:
    git = Mock()
    git.status_porcelain.return_value = "M f.txt" if dirty else ""
    return git


# ── rewind op ──


def test_rewind_head_resets_to_pre_sha_when_clean():
    git = _git()
    result = ReverseCommand(
        op_type="rewind", payload={"pre_sha": "0123456789abcdef"}
    ).execute(git)
    assert result.success
    git.hard_reset_head.assert_called_once_with("0123456789abcdef")


def test_rewind_head_refuses_dirty_worktree():
    git = _git(dirty=True)
    result = ReverseCommand(
        op_type="rewind", payload={"pre_sha": "0123456789abcdef"}
    ).execute(git)
    assert not result.success
    assert "uncommitted" in result.message
    git.hard_reset_head.assert_not_called()


def test_push_rewind_records_payload_and_panel_hint():
    history = SessionHistory()
    history.attach_repo("/repo")
    push_rewind(history, "Merge feat into main", "0123456789abcdef", "Branch")
    record = history.peek(1)[0]
    assert record.description == "Merge feat into main"
    assert record.panel_hint == "Branch"
    assert record.commands[0].op_type == "rewind"
    assert record.commands[0].payload == {"pre_sha": "0123456789abcdef"}


def test_history_reverse_rewind_resets_and_removes_record():
    history = SessionHistory()
    history.attach_repo("/repo")
    push_rewind(history, "Rebase onto main", "abcdef0123456789", "Branch")
    git = _git()
    result = history.reverse(git)
    assert result.success
    git.hard_reset_head.assert_called_once_with("abcdef0123456789")
    assert history.peek(1) == []


# ── describe ──


def test_describe_stage():
    cmd = ReverseCommand(op_type="stage", payload={"path": "a.py"})
    assert cmd.describe() == "git add a.py"


def test_describe_unstage():
    cmd = ReverseCommand(op_type="unstage", payload={"path": "a.py"})
    assert cmd.describe() == "git reset HEAD a.py"


def test_describe_discard_tracked_without_blob_uses_checkout():
    cmd = ReverseCommand(op_type="discard", payload={"path": "a.py", "tracked": True})
    assert cmd.describe() == "git checkout HEAD -- a.py"


def test_describe_discard_tracked_with_blob_uses_backup():
    cmd = ReverseCommand(
        op_type="discard",
        payload={"path": "a.py", "tracked": True, "blob_sha": "bbbb"},
    )
    assert cmd.describe() == "restore a.py (from backup)"


def test_describe_discard_untracked_uses_backup():
    cmd = ReverseCommand(op_type="discard", payload={"path": "a.py", "tracked": False})
    assert cmd.describe() == "restore a.py (from backup)"


def test_describe_ignore_and_unignore_are_semantic():
    assert (
        ReverseCommand(op_type="ignore", payload={"path": "a.py"}).describe()
        == "add a.py to .gitignore"
    )
    assert (
        ReverseCommand(op_type="unignore", payload={"path": "a.py"}).describe()
        == "remove a.py from .gitignore"
    )


def test_describe_commit_is_soft_reset():
    cmd = ReverseCommand(op_type="commit", payload={})
    assert cmd.describe() == "git reset --soft HEAD~1"


def test_describe_rewind_is_hard_reset():
    cmd = ReverseCommand(op_type="rewind", payload={"pre_sha": "0123456789abcdef"})
    assert cmd.describe() == "git reset --hard 0123456"


def test_describe_checkout_and_branch_ops():
    assert (
        ReverseCommand(op_type="checkout_branch", payload={"branch": "dev"}).describe()
        == "git checkout dev"
    )
    assert (
        ReverseCommand(op_type="delete_branch", payload={"name": "feat"}).describe()
        == "git branch feat"
    )
    assert (
        ReverseCommand(
            op_type="rename_branch",
            payload={"old_name": "a", "new_name": "b"},
        ).describe()
        == "git branch -m b a"
    )


def test_describe_stash_ops():
    assert (
        ReverseCommand(op_type="stash_push", payload={}).describe()
        == "git stash pop stash@{0}"
    )
    assert (
        ReverseCommand(
            op_type="stash_pop", payload={"stash_sha": "0123456789abcdef"}
        ).describe()
        == "git stash store 0123456"
    )
    # SHA not yet captured on push → honest placeholder instead of a guess.
    assert (
        ReverseCommand(op_type="stash_pop", payload={}).describe()
        == "git stash store <sha>"
    )


def test_history_describe_commands_joins():
    record = HistoryRecord(
        description="x",
        commands=[
            ReverseCommand(op_type="stage", payload={"path": "a.py"}),
            ReverseCommand(op_type="commit", payload={}),
        ],
        timestamp=0.0,
        panel_hint="status",
    )
    assert record.describe_commands() == "git add a.py、git reset --soft HEAD~1"
