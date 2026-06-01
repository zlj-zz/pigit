"""
Module: pigit/session_history.py
Description: Session-level action history with one-key reversal.
Author: Zev
Date: 2026-06-01
"""

from __future__ import annotations

import base64
import logging
from collections import deque
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal
from collections.abc import Callable

from pigit.viewmodels.base import ActionResult

if TYPE_CHECKING:
    from pigit.git.local_git import LocalGit

_logger = logging.getLogger(__name__)

OpType = Literal[
    "stage",
    "unstage",
    "discard",
    "ignore",
    "unignore",
    "commit",
    "checkout_branch",
    "delete_branch",
    "rename_branch",
    "stash_push",
    "stash_pop",
]


@dataclass
class ReverseCommand:
    """Serializable command that can reverse an action."""

    op_type: OpType
    payload: dict  # plain dict — no object references

    def execute(self, git: LocalGit) -> ActionResult:
        dispatcher = _REVERSE_DISPATCHERS.get(self.op_type)
        if dispatcher is None:
            return ActionResult(
                success=False, message=f"No reverse dispatcher for {self.op_type}"
            )
        try:
            return dispatcher(self.payload, git)
        except Exception as e:
            _logger.exception("Reverse command failed: %s", self.op_type)
            return ActionResult(success=False, message=str(e))


@dataclass
class HistoryRecord:
    """A user-visible action (may contain multiple commands)."""

    description: str
    commands: list[ReverseCommand]
    timestamp: float
    panel_hint: str

    def reverse(self, git: LocalGit) -> ActionResult:
        """Execute inverses in reverse order."""
        for cmd in reversed(self.commands):
            result = cmd.execute(git)
            if not result.success:
                return ActionResult(
                    success=False,
                    message=f"Partial reverse failed at {cmd.op_type}: {result.message}",
                )
        return ActionResult(success=True, message=f"Reversed: {self.description}")


def _estimate_memory(record: HistoryRecord) -> int:
    """Estimate memory cost of a record (for eviction)."""
    cost = 0
    for cmd in record.commands:
        payload = cmd.payload
        if "content_b64" in payload:
            # base64 is ~4/3 of raw; approximate raw size
            cost += int(len(payload["content_b64"]) * 0.75)
    return cost


class SessionHistory:
    """LIFO stack of reversible actions for the current session."""

    def __init__(self, max_items: int = 100, max_memory_mb: int = 50) -> None:
        self._stack: deque[HistoryRecord] = deque()
        self._max_items = max_items
        self._max_memory = max_memory_mb * 1024 * 1024
        self._current_memory = 0
        self._prev_branch: str | None = None

    def push(self, record: HistoryRecord) -> None:
        cost = _estimate_memory(record)
        self._evict_if_needed(cost)
        self._stack.append(record)
        self._current_memory += cost

    def reverse(self, git: LocalGit) -> ActionResult:
        if not self._stack:
            return ActionResult(success=False, message="Nothing to reverse")
        record = self._stack.pop()
        result = record.reverse(git)
        if result.success:
            self._current_memory -= _estimate_memory(record)
        # Truncate on failure — timeline is broken.
        return result

    def reverse_to(self, index: int, git: LocalGit) -> ActionResult:
        """Rewind: reverse all items from top down to index (inclusive)."""
        n = len(self._stack)
        if index < 0 or index >= n:
            return ActionResult(success=False, message="Invalid index")
        reversed_count = 0
        for i, record in enumerate(reversed(self._stack)):
            if i > index:
                break
            result = record.reverse(git)
            if not result.success:
                # Truncate stack: remove already-reversed items
                for _ in range(reversed_count):
                    self._stack.pop()
                return ActionResult(
                    success=False,
                    message=f"Partial reverse at step {i + 1}: {result.message}",
                )
            reversed_count += 1
        # Remove reversed records from stack
        for _ in range(reversed_count):
            popped = self._stack.pop()
            self._current_memory -= _estimate_memory(popped)
        return ActionResult(
            success=True, message=f"Reversed {reversed_count} action(s)"
        )

    def peek(self, n: int = 20) -> list[HistoryRecord]:
        """Return the N most recent records (newest first)."""
        from itertools import islice

        return list(islice(reversed(self._stack), n))

    def _evict_if_needed(self, incoming_cost: int) -> None:
        while (
            len(self._stack) >= self._max_items
            or self._current_memory + incoming_cost > self._max_memory
        ):
            if not self._stack:
                break
            evicted = self._stack.popleft()
            self._current_memory -= _estimate_memory(evicted)
            _logger.debug("Evicted history record: %s", evicted.description)

    def on_pre_checkout(self, current_branch: str) -> None:
        """Call before checkout to remember the previous branch."""
        self._prev_branch = current_branch

    @property
    def prev_branch(self) -> str | None:
        return self._prev_branch


# ------------------------------------------------------------------
# Reverse dispatchers
# ------------------------------------------------------------------


def _stage_file(payload: dict, git: LocalGit) -> ActionResult:
    path = payload["path"]
    git.add_file(path)
    return ActionResult(success=True, message=f"Restored (staged) {path}")


def _unstage_file(payload: dict, git: LocalGit) -> ActionResult:
    path = payload["path"]
    git.reset_head_file(path)
    return ActionResult(success=True, message=f"Restored (unstaged) {path}")


def _restore_file(payload: dict, git: LocalGit) -> ActionResult:
    path = payload["path"]
    if payload.get("tracked"):
        blob_sha = payload.get("blob_sha")
        if blob_sha:
            git.cat_file_to_path(blob_sha, path)
        else:
            git.checkout_head_file(path)
    else:
        content_b64 = payload.get("content_b64")
        if content_b64:
            data = base64.b64decode(content_b64)
            git.write_file_bytes(path, data)
        else:
            return ActionResult(
                success=False, message=f"Cannot restore {path}: content missing"
            )
    return ActionResult(success=True, message=f"Restored {path}")


def _ignore_file(payload: dict, git: LocalGit) -> ActionResult:
    path = payload["path"]
    git.ignore_file(path)
    return ActionResult(success=True, message=f"Restored (ignored) {path}")


def _unignore_file(payload: dict, git: LocalGit) -> ActionResult:
    path = payload["path"]
    git.unignore_file(path)
    return ActionResult(success=True, message=f"Restored (unignored) {path}")


def _soft_reset_head1(_payload: dict, git: LocalGit) -> ActionResult:  # noqa: ARG001
    git.soft_reset_head1()
    return ActionResult(success=True, message="Uncommitted (changes re-staged)")


def _checkout_branch(payload: dict, git: LocalGit) -> ActionResult:
    branch = payload["branch"]
    git.checkout_branch(branch)
    return ActionResult(success=True, message=f"Restored branch: {branch}")


def _create_branch(payload: dict, git: LocalGit) -> ActionResult:
    name = payload["name"]
    sha = payload.get("sha")
    if sha:
        git.create_branch_at(name, sha)
    else:
        git.create_branch(name)
    return ActionResult(success=True, message=f"Restored branch: {name}")


def _rename_branch(payload: dict, git: LocalGit) -> ActionResult:
    old_name = payload["old_name"]
    new_name = payload["new_name"]
    git.rename_branch(new_name, old_name)
    return ActionResult(success=True, message=f"Restored branch name: {old_name}")


def _stash_pop(_payload: dict, git: LocalGit) -> ActionResult:  # noqa: ARG001
    git.stash_pop("stash@{0}")
    return ActionResult(success=True, message="Restored stash")


def _stash_store(payload: dict, git: LocalGit) -> ActionResult:
    sha = payload["stash_sha"]
    git.stash_store(sha)
    return ActionResult(success=True, message="Restored stash")


_REVERSE_DISPATCHERS: dict[OpType, Callable[[dict, LocalGit], ActionResult]] = {
    "stage": _stage_file,
    "unstage": _unstage_file,
    "discard": _restore_file,
    "ignore": _ignore_file,
    "unignore": _unignore_file,
    "commit": _soft_reset_head1,
    "checkout_branch": _checkout_branch,
    "delete_branch": _create_branch,
    "rename_branch": _rename_branch,
    "stash_push": _stash_pop,
    "stash_pop": _stash_store,
}
