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
    # The reversal re-stores the entry at stash@{0}; say so rather than
    # implying the original index comes back.
    assert (
        ReverseCommand(
            op_type="stash_pop", payload={"stash_sha": "0123456789abcdef"}
        ).describe()
        == "git stash store 0123456 (as stash@{0})"
    )
    # No SHA (a record the VM refuses to push today) → honest placeholder
    # instead of a guess. describe renders inside the confirm dialog, so it
    # must not raise on this payload either.
    assert (
        ReverseCommand(op_type="stash_pop", payload={}).describe()
        == "git stash store <sha>"
    )


def test_create_branch_reverse_deletes_without_force():
    """Non-force on purpose: if commits landed on the branch since, git
    refuses and the user keeps them."""
    git = _git()
    result = ReverseCommand(op_type="create_branch", payload={"name": "feat"}).execute(
        git
    )
    assert result.success
    git.delete_branch.assert_called_once_with("feat")


def test_amend_reverse_soft_resets_to_pre_sha():
    git = _git()
    result = ReverseCommand(
        op_type="amend", payload={"pre_sha": "0123456789abcdef"}
    ).execute(git)
    assert result.success
    git.soft_reset_head.assert_called_once_with("0123456789abcdef")


def test_describe_create_branch_and_amend():
    assert (
        ReverseCommand(op_type="create_branch", payload={"name": "feat"}).describe()
        == "git branch -d feat"
    )
    assert (
        ReverseCommand(
            op_type="amend", payload={"pre_sha": "0123456789abcdef"}
        ).describe()
        == "git reset --soft 0123456"
    )


def test_stash_pop_reverse_stores_the_captured_sha():
    """Regression: an empty payload made the reversal fail with 'stash_sha'.

    The record is popped off the stack before its reversal runs, so that
    failure silently ate the user's only chance to undo the pop.
    """
    git = _git()
    result = ReverseCommand(
        op_type="stash_pop", payload={"stash_sha": "0123456789abcdef"}
    ).execute(git)
    assert result.success
    git.stash_store.assert_called_once_with("0123456789abcdef")


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
    # Shown in the undo confirm dialog's "Run:" line, so the separator is
    # the UI's own comma, not a fullwidth one.
    assert record.describe_commands() == "git add a.py, git reset --soft HEAD~1"
