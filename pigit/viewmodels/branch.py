"""
Module: pigit/viewmodels/branch.py
Description: BranchPanel ViewModel.
Author: Zev
Date: 2026-05-25
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING
from collections.abc import Callable

from .base import (
    ActionResult,
    IListViewModel,
    ViewModelBase,
    WorktreeGate,
    run_gated,
)
from pigit.session_history import SessionHistory, HistoryRecord, ReverseCommand

if TYPE_CHECKING:
    from pigit.app_types import BranchSnapshot
    from pigit.git.api import GitApi
    from pigit.git.model import Branch

_logger = logging.getLogger(__name__)

_DIRTY_WORKTREE = "Uncommitted changes, stash or commit first"
# A probe that raised must never read as "go ahead" — the merge would start on
# a worktree whose state we could not even inspect.
_UNKNOWN_WORKTREE = "Cannot read working tree state — check Status first"


class IBranchViewModel(IListViewModel["Branch"]):
    """Protocol for BranchPanel's ViewModel."""

    @property
    def scope(self) -> str: ...
    def set_scope(self, scope: str) -> None: ...
    def checkout(self, idx: int) -> ActionResult: ...
    def create_branch(self, name: str) -> ActionResult: ...
    def rename_branch(self, idx: int, new_name: str) -> ActionResult: ...
    def delete_branch(self, idx: int, force: bool = False) -> ActionResult: ...
    def get_inspector_snapshot(self, idx: int) -> BranchSnapshot | None: ...
    def current_branch(self) -> str: ...
    def can_merge(self) -> tuple[bool, str]: ...
    def can_rebase(self) -> tuple[bool, str]: ...
    def get_remote_url(self) -> str: ...
    def load_log_graph(self, branch_name: str) -> list[str]: ...


class BranchViewModel(ViewModelBase["Branch"], IBranchViewModel):
    """Concrete ViewModel for branch list."""

    _SCOPES = ["local", "remote", "all"]
    load_label = "Branches"

    def __init__(
        self,
        git: GitApi,
        history: SessionHistory | None = None,
        *,
        worktree_gate: WorktreeGate,
    ) -> None:
        super().__init__()
        self._git = git
        self._history = history
        self._worktree_gate = worktree_gate
        self._scope: str = "local"

    @property
    def scope(self) -> str:
        return self._scope

    def set_scope(self, scope: str) -> None:
        self._scope = scope

    def _do_load(self) -> list[Branch]:
        return self._git.load_branches(scope=self._scope)

    def checkout(self, idx: int) -> ActionResult:
        return run_gated(self._worktree_gate, lambda: self._checkout(idx))

    def _checkout(self, idx: int) -> ActionResult:
        b = self.item_at(idx)
        if b is None:
            return ActionResult(success=False, message="Invalid index")
        current = self._git.get_head() or ""
        try:
            if self._history is not None:
                self._history.on_pre_checkout(current)
            self._git.checkout_branch(b.name)
            result = ActionResult(
                success=True, message=f"Switched to {b.name}", should_refresh=True
            )
        except Exception as e:
            return ActionResult(success=False, message=str(e))
        if result.success and self._history is not None:
            cmd = ReverseCommand(
                op_type="checkout_branch",
                payload={"branch": current},
            )
            self._history.push(
                HistoryRecord(
                    description=f"Checked out {b.name}",
                    commands=[cmd],
                    timestamp=time.time(),
                    panel_hint="branch",
                )
            )
        return result

    def create_branch(self, name: str) -> ActionResult:
        """Create *name* and switch to it (``git checkout -b``)."""
        return run_gated(self._worktree_gate, lambda: self._create_branch(name))

    def _create_branch(self, name: str) -> ActionResult:
        current = self._git.get_head() or ""
        try:
            if self._history is not None:
                self._history.on_pre_checkout(current)
            self._git.create_branch(name)
        except Exception as e:
            return ActionResult(success=False, message=str(e))
        if self._history is not None and current:
            # reverse() walks ``commands`` backwards, so the checkout back is
            # listed last and therefore runs first — deleting the branch HEAD
            # is sitting on would fail.
            self._history.push(
                HistoryRecord(
                    description=f"Created branch {name}",
                    commands=[
                        ReverseCommand(op_type="create_branch", payload={"name": name}),
                        ReverseCommand(
                            op_type="checkout_branch", payload={"branch": current}
                        ),
                    ],
                    timestamp=time.time(),
                    panel_hint="branch",
                )
            )
        return ActionResult(
            success=True,
            message=f"Created and switched to {name}",
            should_refresh=True,
        )

    def rename_branch(self, idx: int, new_name: str) -> ActionResult:
        b = self.item_at(idx)
        if b is None:
            return ActionResult(success=False, message="Invalid index")
        old_name = b.name
        try:
            self._git.rename_branch(old_name, new_name)
            result = ActionResult(
                success=True, message=f"Renamed to {new_name}", should_refresh=True
            )
        except Exception as e:
            return ActionResult(success=False, message=str(e))
        if result.success and self._history is not None:
            cmd = ReverseCommand(
                op_type="rename_branch",
                payload={"old_name": old_name, "new_name": new_name},
            )
            self._history.push(
                HistoryRecord(
                    description=f"Renamed {old_name} → {new_name}",
                    commands=[cmd],
                    timestamp=time.time(),
                    panel_hint="branch",
                )
            )
        return result

    def delete_branch(self, idx: int, force: bool = False) -> ActionResult:
        b = self.item_at(idx)
        if b is None:
            return ActionResult(success=False, message="Invalid index")
        # Capture branch SHA before deletion for potential restore
        sha = self._git.get_head() if b.is_head else self._git._branch_sha(b.name)
        try:
            self._git.delete_branch(b.name, force=force)
            result = ActionResult(
                success=True, message=f"Deleted {b.name}", should_refresh=True
            )
        except Exception as e:
            return ActionResult(success=False, message=str(e))
        if result.success and self._history is not None:
            cmd = ReverseCommand(
                op_type="delete_branch",
                payload={"name": b.name, "sha": sha or ""},
            )
            self._history.push(
                HistoryRecord(
                    description=f"Deleted {b.name}",
                    commands=[cmd],
                    timestamp=time.time(),
                    panel_hint="branch",
                )
            )
        return result

    def get_inspector_snapshot(self, idx: int):
        b = self.item_at(idx)
        if b is None:
            return None
        return self._memo_inspector(
            ("branch", b.name), lambda: self._build_branch_snapshot(b)
        )

    def _build_branch_snapshot(self, b: Branch):
        from pigit.app_types import BranchSnapshot
        from pigit.git.api import GitError

        tip = ""
        contained: bool | None = None
        try:
            tip = self._git.verify_commitish(b.name)
            contained = self._git.is_ancestor(tip)
        except GitError:
            # Stale/deleted ref or shallow-clone gap: keep identity and mark
            # ancestry unknown instead of aborting the whole snapshot.
            if not tip:
                tip = self._git._branch_sha(b.name) or ""
        created = self._git.get_branch_creation_time(b.name)
        if created == "?":
            created = None
        recent_msg, recent_author = self._git.get_branch_recent_commit(b.name)
        return BranchSnapshot(
            identity=b.name,
            tip=tip,
            created=created,
            contained=contained,
            current="yes" if b.is_head else "no",
            upstream=b.upstream_name or "none",
            ahead=b.ahead if b.ahead != "?" else "0",
            behind=b.behind if b.behind != "?" else "0",
            recent_msg=recent_msg,
            recent_author=recent_author,
        )

    def current_branch(self) -> str:
        return self._git.get_head() or ""

    def _worktree_ready(self, probe: Callable[[], bool]) -> tuple[bool, str]:
        """Return ``(ok, reason)`` for an operation needing a clean worktree.

        Args:
            probe: Returns True when the worktree has uncommitted changes.

        Returns:
            ``(False, reason)`` when the probe says dirty *or* when it raised,
            ``(True, "")`` when the worktree is clean.
        """
        try:
            dirty = probe()
        except Exception:
            _logger.exception("Worktree probe failed")
            return False, _UNKNOWN_WORKTREE
        if dirty:
            return False, _DIRTY_WORKTREE
        return True, ""

    def can_merge(self) -> tuple[bool, str]:
        return self._worktree_ready(
            lambda: self._git.has_staged_changes() or self._git.has_untracked_changes()
        )

    def can_rebase(self) -> tuple[bool, str]:
        return self._worktree_ready(
            lambda: self._git.has_staged_changes()
            or self._git.has_unstaged_changes()
            or self._git.has_untracked_changes()
        )

    def get_remote_url(self) -> str:
        """Return the primary remote URL string, or empty."""
        return self._git.get_remote_url() or ""

    def load_log_graph(self, branch_name: str) -> list[str]:
        """Return native ``git log --decorate --graph`` lines for ``branch_name``.

        The commit cap comes from ``LOG_GRAPH_LIMIT`` (owned by GitApi).

        Args:
            branch_name: Ref to log (short name, e.g. ``origin/foo``).

        Returns:
            Graph lines with trailing empty lines stripped by GitApi.
        """
        text = self._git.load_log_graph(branch_name)
        if not text:
            return []
        return text.splitlines()
