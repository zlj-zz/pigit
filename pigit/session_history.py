"""
Module: pigit/session_history.py
Description: Session-level action history with one-key reversal.
Author: Zev
Date: 2026-06-01
"""

from __future__ import annotations

import base64
import logging
import time
from collections import deque
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, NamedTuple
from collections.abc import Callable

if TYPE_CHECKING:
    # ``pigit.viewmodels`` eagerly imports session_history (via the branch
    # VM), so ActionResult must not be a module-level name here: every
    # function that builds one imports it lazily to avoid a runtime
    # circular import (session_history → viewmodels → session_history).
    from pigit.git.api import GitApi
    from pigit.viewmodels.base import ActionResult

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
    "rewind",
]


@dataclass
class ReverseCommand:
    """Serializable command that can reverse an action."""

    op_type: OpType
    payload: dict  # plain dict — no object references

    def execute(self, git: GitApi) -> ActionResult:
        from pigit.viewmodels.base import ActionResult

        spec = _REVERSE_SPECS.get(self.op_type)
        if spec is None:
            return ActionResult(
                success=False, message=f"No reverse dispatcher for {self.op_type}"
            )
        try:
            return spec.exec(self.payload, git)
        except Exception as e:
            _logger.exception("Reverse command failed: %s", self.op_type)
            return ActionResult(success=False, message=str(e))

    def describe(self) -> str:
        """Render the git command this reversal will run (payload only).

        No git calls — the confirm dialog must not spawn subprocesses.
        """
        spec = _REVERSE_SPECS.get(self.op_type)
        if spec is None:
            return f"reverse {self.op_type}"
        return spec.describe(self.payload)


@dataclass
class HistoryRecord:
    """A user-visible action (may contain multiple commands)."""

    description: str
    commands: list[ReverseCommand]
    timestamp: float
    panel_hint: str
    repo_path: str = ""

    def reverse(self, git: GitApi) -> ActionResult:
        """Execute inverses in reverse order."""
        from pigit.viewmodels.base import ActionResult

        for cmd in reversed(self.commands):
            result = cmd.execute(git)
            if not result.success:
                return ActionResult(
                    success=False,
                    message=f"Partial reverse failed at {cmd.op_type}: {result.message}",
                )
        return ActionResult(success=True, message=f"Reversed: {self.description}")

    def describe_commands(self) -> str:
        """Join the commands this reversal will run, for confirm dialogs."""
        return "、".join(cmd.describe() for cmd in self.commands)


def _estimate_memory(record: HistoryRecord) -> int:
    """Estimate memory cost of a record (for eviction)."""
    cost = 0
    for cmd in record.commands:
        payload = cmd.payload
        if "content_b64" in payload:
            # base64 is ~4/3 of raw; approximate raw size
            cost += int(len(payload["content_b64"]) * 0.75)
    return cost


_FOREIGN_REPO_HISTORY = "History belongs to another repository"


class SessionHistory:
    """LIFO stack of reversible actions for the current session.

    Records are stamped with :attr:`_active_repo` on push. ``u`` / Recent
    only reverse or list entries for that path (multi-repo TUI isolation).
    """

    def __init__(self, max_items: int = 100, max_memory_mb: int = 50) -> None:
        self._stack: deque[HistoryRecord] = deque()
        self._max_items = max_items
        self._max_memory = max_memory_mb * 1024 * 1024
        self._current_memory = 0
        self._prev_branch: str | None = None
        self._active_repo: str = ""

    def attach_repo(self, repo_path: str) -> None:
        """Bind undo visibility to ``repo_path`` (call on session switch)."""
        self._active_repo = repo_path

    def push(self, record: HistoryRecord) -> None:
        if not record.repo_path:
            record.repo_path = self._active_repo
        cost = _estimate_memory(record)
        self._evict_if_needed(cost)
        self._stack.append(record)
        self._current_memory += cost

    def reverse(self, git: GitApi) -> ActionResult:
        """Reverse the newest record for the active repository."""
        from pigit.viewmodels.base import ActionResult

        index = self._newest_index_for_active()
        if index is None:
            if self._stack:
                return ActionResult(success=False, message=_FOREIGN_REPO_HISTORY)
            return ActionResult(success=False, message="Nothing to reverse")
        record = self._pop_at(index)
        # Record is removed from the stack either way (truncate on failure),
        # so its memory cost leaves the budget regardless of outcome.
        self._current_memory -= _estimate_memory(record)
        result = record.reverse(git)
        # Truncate on failure — timeline is broken (record already removed).
        return result

    def reverse_to(self, index: int, git: GitApi) -> ActionResult:
        """Rewind active-repo records from newest down to ``index`` (inclusive).

        ``index`` is into :meth:`peek` (0 = newest visible), not the raw stack.
        """
        from pigit.viewmodels.base import ActionResult

        visible = self._records_for_active()
        if index < 0 or index >= len(visible):
            return ActionResult(success=False, message="Invalid index")
        to_reverse = visible[: index + 1]
        reversed_count = 0
        for step, record in enumerate(to_reverse):
            result = record.reverse(git)
            if not result.success:
                for done in to_reverse[:reversed_count]:
                    self._remove_record(done)
                    self._current_memory -= _estimate_memory(done)
                return ActionResult(
                    success=False,
                    message=f"Partial reverse at step {step + 1}: {result.message}",
                )
            reversed_count += 1
        for record in to_reverse:
            self._remove_record(record)
            self._current_memory -= _estimate_memory(record)
        return ActionResult(
            success=True, message=f"Reversed {reversed_count} action(s)"
        )

    def peek(self, n: int = 20) -> list[HistoryRecord]:
        """Return up to N newest records for the active repository."""
        return self._records_for_active()[:n]

    def _records_for_active(self) -> list[HistoryRecord]:
        """Newest-first records stamped with the active repo path."""
        return [
            record
            for record in reversed(self._stack)
            if record.repo_path == self._active_repo
        ]

    def _newest_index_for_active(self) -> int | None:
        """Stack index (0 = oldest) of the newest active-repo record."""
        for index in range(len(self._stack) - 1, -1, -1):
            if self._stack[index].repo_path == self._active_repo:
                return index
        return None

    def _pop_at(self, index: int) -> HistoryRecord:
        """Remove and return ``self._stack[index]`` (0 = oldest)."""
        self._stack.rotate(-index)
        record = self._stack.popleft()
        self._stack.rotate(index)
        return record

    def _remove_record(self, record: HistoryRecord) -> None:
        """Remove a specific record instance from the stack."""
        for index, item in enumerate(self._stack):
            if item is record:
                self._pop_at(index)
                return

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


def _stage_file(payload: dict, git: GitApi) -> ActionResult:
    from pigit.viewmodels.base import ActionResult

    path = payload["path"]
    git.add_file(path)
    return ActionResult(success=True, message=f"Restored (staged) {path}")


def _unstage_file(payload: dict, git: GitApi) -> ActionResult:
    from pigit.viewmodels.base import ActionResult

    path = payload["path"]
    git.reset_head_file(path)
    return ActionResult(success=True, message=f"Restored (unstaged) {path}")


def _restore_file(payload: dict, git: GitApi) -> ActionResult:
    from pigit.viewmodels.base import ActionResult

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


def _ignore_file(payload: dict, git: GitApi) -> ActionResult:
    from pigit.viewmodels.base import ActionResult

    path = payload["path"]
    git.ignore_file(path)
    return ActionResult(success=True, message=f"Restored (ignored) {path}")


def _unignore_file(payload: dict, git: GitApi) -> ActionResult:
    from pigit.viewmodels.base import ActionResult

    path = payload["path"]
    git.unignore_file(path)
    return ActionResult(success=True, message=f"Restored (unignored) {path}")


def _soft_reset_head1(_payload: dict, git: GitApi) -> ActionResult:  # noqa: ARG001
    from pigit.viewmodels.base import ActionResult

    git.soft_reset_head1()
    return ActionResult(success=True, message="Uncommitted (changes re-staged)")


def _checkout_branch(payload: dict, git: GitApi) -> ActionResult:
    from pigit.viewmodels.base import ActionResult

    branch = payload["branch"]
    git.checkout_branch(branch)
    return ActionResult(success=True, message=f"Restored branch: {branch}")


def _create_branch(payload: dict, git: GitApi) -> ActionResult:
    from pigit.viewmodels.base import ActionResult

    name = payload["name"]
    sha = payload.get("sha")
    if sha:
        git.create_branch_at(name, sha)
    else:
        git.create_branch(name)
    return ActionResult(success=True, message=f"Restored branch: {name}")


def _rename_branch(payload: dict, git: GitApi) -> ActionResult:
    from pigit.viewmodels.base import ActionResult

    old_name = payload["old_name"]
    new_name = payload["new_name"]
    git.rename_branch(new_name, old_name)
    return ActionResult(success=True, message=f"Restored branch name: {old_name}")


def _stash_pop(_payload: dict, git: GitApi) -> ActionResult:  # noqa: ARG001
    from pigit.viewmodels.base import ActionResult

    git.stash_pop("stash@{0}")
    return ActionResult(success=True, message="Restored stash")


def _stash_store(payload: dict, git: GitApi) -> ActionResult:
    from pigit.viewmodels.base import ActionResult

    sha = payload["stash_sha"]
    git.stash_store(sha)
    return ActionResult(success=True, message="Restored stash")


def rewind_head(payload: dict, git: GitApi) -> ActionResult:
    """Reset HEAD to a recorded SHA; refuse when the worktree is dirty.

    ``git reset --hard`` would discard uncommitted changes made after the
    operation, so guard on ``status_porcelain`` before touching HEAD.
    """
    from pigit.viewmodels.base import ActionResult

    if git.status_porcelain().strip():
        return ActionResult(
            success=False,
            message="Undo would discard uncommitted changes — commit or stash first",
        )
    git.hard_reset_head(payload["pre_sha"])
    return ActionResult(success=True, message=f"Rewound to {payload['pre_sha'][:7]}")


def push_rewind(
    history: SessionHistory,
    description: str,
    pre_sha: str,
    panel_hint: str,
) -> None:
    """Record one HEAD-moving operation for later ``u`` reversal."""
    history.push(
        HistoryRecord(
            description=description,
            commands=[ReverseCommand(op_type="rewind", payload={"pre_sha": pre_sha})],
            timestamp=time.time(),
            panel_hint=panel_hint,
        )
    )


class _ReverseSpec(NamedTuple):
    """How to reverse an op and how to describe the reversal command.

    One registry entry per op keeps the execution logic and the confirm-dialog
    description in lockstep — no duplicate dictionary to drift.
    """

    exec: Callable[[dict, GitApi], ActionResult]
    describe: Callable[[dict], str]


_REVERSE_SPECS: dict[OpType, _ReverseSpec] = {
    "stage": _ReverseSpec(_stage_file, lambda p: f"git add {p['path']}"),
    "unstage": _ReverseSpec(_unstage_file, lambda p: f"git reset HEAD {p['path']}"),
    # Discard restores tracked files from HEAD unless a blob backup exists;
    # describe the actual branch so the confirm dialog cannot mislead.
    "discard": _ReverseSpec(
        _restore_file,
        lambda p: (
            f"git checkout HEAD -- {p['path']}"
            if p.get("tracked") and not p.get("blob_sha")
            else f"restore {p['path']} (from backup)"
        ),
    ),
    # git has no .gitignore subcommand; the semantic text is clearer than a
    # fabricated command.
    "ignore": _ReverseSpec(_ignore_file, lambda p: f"add {p['path']} to .gitignore"),
    "unignore": _ReverseSpec(
        _unignore_file, lambda p: f"remove {p['path']} from .gitignore"
    ),
    "commit": _ReverseSpec(_soft_reset_head1, lambda _p: "git reset --soft HEAD~1"),
    "checkout_branch": _ReverseSpec(
        _checkout_branch,
        lambda p: f"git checkout {p['branch']}",
    ),
    "delete_branch": _ReverseSpec(_create_branch, lambda p: f"git branch {p['name']}"),
    "rename_branch": _ReverseSpec(
        _rename_branch,
        lambda p: f"git branch -m {p['new_name']} {p['old_name']}",
    ),
    "stash_push": _ReverseSpec(_stash_pop, lambda _p: "git stash pop stash@{0}"),
    # Stash restore needs the stashed SHA (not yet captured on push); render
    # the real short SHA when present so the confirm dialog shows the truth.
    "stash_pop": _ReverseSpec(
        _stash_store,
        lambda p: (
            f"git stash store {p['stash_sha'][:7]}"
            if p.get("stash_sha")
            else "git stash store <sha>"
        ),
    ),
    "rewind": _ReverseSpec(
        rewind_head, lambda p: f"git reset --hard {p['pre_sha'][:7]}"
    ),
}
