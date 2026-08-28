"""
Module: pigit/git/api/_worktrees.py
Description: Git worktree feature ops (list/add/remove), distinct from _worktree file ops.
Author: Zev
Date: 2026-08-28
"""

from __future__ import annotations

import shlex
from dataclasses import dataclass

from pigit.ext.executor import WAITING, REPLY, DECODE

from ._base import _OpsBase
from ._errors import GitError


@dataclass(frozen=True)
class WorktreeInfo:
    """One linked working tree from ``git worktree list --porcelain``."""

    path: str
    head_sha: str
    branch: str | None
    is_main: bool
    detached: bool = False


def parse_worktree_porcelain(text: str) -> list[WorktreeInfo]:
    """Parse ``git worktree list --porcelain`` into :class:`WorktreeInfo` rows.

    Detached trees may emit an explicit ``detached`` line and/or omit ``branch``;
    both forms are treated as detached. The first entry is the main worktree.
    """
    entries: list[WorktreeInfo] = []
    path: str | None = None
    head_sha = ""
    branch: str | None = None
    detached = False

    def _flush() -> None:
        nonlocal path, head_sha, branch, detached
        if path is None:
            return
        is_detached = detached or branch is None
        entries.append(
            WorktreeInfo(
                path=path,
                head_sha=head_sha,
                branch=None if is_detached else branch,
                is_main=len(entries) == 0,
                detached=is_detached,
            )
        )
        path = None
        head_sha = ""
        branch = None
        detached = False

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            _flush()
            continue
        if line.startswith("worktree "):
            _flush()
            path = line[len("worktree ") :]
            continue
        if line.startswith("HEAD "):
            head_sha = line[len("HEAD ") :]
            continue
        if line.startswith("branch "):
            ref = line[len("branch ") :]
            branch = ref[len("refs/heads/") :] if ref.startswith("refs/heads/") else ref
            detached = False
            continue
        if line == "detached":
            detached = True
            branch = None
            continue
        # Ignore bare / locked / prunable / other porcelain keys.
    _flush()
    return entries


class _WorktreesOps(_OpsBase):
    """``git worktree`` list / add / remove and linked-worktree detection."""

    def list_worktrees(self, path: str | None = None) -> list[WorktreeInfo]:
        """Return all worktrees for the repository at ``path``."""
        path = path or self.path
        code, err, out = self.executor.exec(
            "git worktree list --porcelain",
            flags=WAITING | REPLY | DECODE,
            cwd=path,
        )
        if code != 0:
            raise GitError(err or "Failed to list worktrees")
        text = "" if out is None else str(out)
        return parse_worktree_porcelain(text)

    def add_worktree(
        self,
        target: str,
        branch: str,
        *,
        new: bool = True,
        path: str | None = None,
    ) -> None:
        """Create a worktree at ``target`` for ``branch``.

        Args:
            target: Absolute or relative path for the new working tree.
            branch: Branch name to check out.
            new: When True, create ``branch`` with ``-b`` (required for a new
                branch). When False, check out an existing branch.
            path: Repository path used as cwd for the git command.
        """
        path = path or self.path
        if new:
            cmd = "git worktree add -b " f"{shlex.quote(branch)} {shlex.quote(target)}"
        else:
            cmd = "git worktree add " f"{shlex.quote(target)} {shlex.quote(branch)}"
        code, err, _ = self.executor.exec(
            cmd,
            flags=WAITING | REPLY | DECODE,
            cwd=path,
        )
        if code != 0:
            raise GitError(err or f"Failed to add worktree: {target}")

    def remove_worktree(
        self,
        target: str,
        *,
        force: bool = False,
        path: str | None = None,
    ) -> None:
        """Remove the worktree at ``target`` (``--force`` when requested)."""
        path = path or self.path
        force_flag = "--force " if force else ""
        cmd = f"git worktree remove {force_flag}{shlex.quote(target)}"
        code, err, _ = self.executor.exec(
            cmd,
            flags=WAITING | REPLY | DECODE,
            cwd=path,
        )
        if code != 0:
            raise GitError(err or f"Failed to remove worktree: {target}")

    def is_worktree(self, path: str | None = None) -> bool:
        """Return True when ``path`` is a linked worktree (not the main tree).

        A linked worktree reports different ``--git-dir`` (under
        ``.git/worktrees/<name>``) and ``--git-common-dir`` (the shared
        ``.git``); the main tree reports the same directory for both. This
        compares semantics rather than string-matching a ``worktrees`` path
        segment, which would misfire when the main tree itself lives under a
        directory named ``worktrees``.
        """
        path = path or self.path
        code, err, out = self.executor.exec(
            "git rev-parse --git-dir",
            flags=WAITING | REPLY | DECODE,
            cwd=path,
        )
        if code != 0 or not out:
            raise GitError(err or "Failed to resolve git-dir")
        git_dir = str(out).strip()
        code, err, out = self.executor.exec(
            "git rev-parse --git-common-dir",
            flags=WAITING | REPLY | DECODE,
            cwd=path,
        )
        if code != 0 or not out:
            raise GitError(err or "Failed to resolve git-common-dir")
        common_dir = str(out).strip()
        return git_dir != common_dir
