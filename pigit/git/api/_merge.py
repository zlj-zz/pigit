"""
Module: pigit/git/api/_merge.py
Description: Merge, pull, commit, and cherry-pick sequencer operations.
Author: Zev
Date: 2026-08-13
"""

from __future__ import annotations

import os
import shlex
from pathlib import Path
from typing import cast

from pigit.ext.executor import WAITING, REPLY, DECODE

from ._base import _OpsBase
from ._errors import GitError, SequencerPaused


class _MergeOps(_OpsBase):
    """Merge, pull, and commit operations."""

    def __init__(self, api, core) -> None:
        super().__init__(api)
        self._core = core

    def pull(self, path: str | None = None) -> None:
        """Pull from the upstream remote. Raises GitError on failure."""
        path = path or self.path
        code, err, _out = self.executor.exec(
            "git pull",
            cwd=path,
            flags=WAITING | REPLY | DECODE,
        )
        if code != 0:
            raise GitError(err or "Pull failed")

    def merge(self, source: str, path: str | None = None) -> None:
        """Merge ``source`` into the current branch. Raises GitError on failure.

        If the merge results in conflicts, the error message will contain
        the word "conflict" so the caller can detect it.
        """
        path = path or self.path
        code, err, _out = self.executor.exec(
            f"git merge {shlex.quote(source)}",
            cwd=path,
            flags=WAITING | REPLY | DECODE,
        )
        if code != 0:
            msg = cast(str, err) if err else f"Merge failed: {source}"
            if code == 1 and ("conflict" in msg.lower() or "CONFLICT" in msg):
                raise GitError(f"Merge conflict: {msg}")
            raise GitError(msg)

    def sequencer_in_progress(self, path: str | None = None) -> str | None:
        """Return the active sequencer kind, or None if the tree is clean.

        Order: merge, rebase, cherry-pick, revert.
        """
        try:
            git_dir = Path(self._core.get_git_dir(path))
        except GitError:
            return None
        if (git_dir / "MERGE_HEAD").exists():
            return "merge"
        if (git_dir / "rebase-merge").exists() or (git_dir / "rebase-apply").exists():
            return "rebase"
        if (git_dir / "CHERRY_PICK_HEAD").exists():
            return "cherry-pick"
        if (git_dir / "REVERT_HEAD").exists():
            return "revert"
        return None

    def is_merge_in_progress(self, path: str | None = None) -> bool:
        """Return True if MERGE_HEAD exists in the git directory."""
        return self.sequencer_in_progress(path) == "merge"

    def is_rebase_in_progress(self, path: str | None = None) -> bool:
        """Return True if a rebase is in progress (rebase-merge or rebase-apply dir)."""
        return self.sequencer_in_progress(path) == "rebase"

    def resolve_head_sha(self, path: str | None = None) -> str:
        """Return the full SHA of HEAD via ``git rev-parse HEAD``."""
        path = path or self.path
        code, err, out = self.executor.exec(
            "git rev-parse HEAD",
            cwd=path,
            flags=WAITING | REPLY | DECODE,
        )
        if code != 0 or not out:
            raise GitError(err or "Failed to resolve HEAD")
        return cast(str, out).strip()

    def has_unmerged_paths(self, path: str | None = None) -> bool:
        """Return True if ``git diff`` lists unmerged (conflicted) paths."""
        path = path or self.path
        code, err, out = self.executor.exec(
            "git diff --name-only --diff-filter=U",
            cwd=path,
            flags=WAITING | REPLY | DECODE,
        )
        if code != 0:
            raise GitError(err or "Failed to list unmerged paths")
        return bool(cast(str, out or "").strip())

    def cherry_pick(self, sha: str, path: str | None = None) -> None:
        """Apply ``sha`` onto HEAD. Raises SequencerPaused if CHERRY_PICK_HEAD remains."""
        path = path or self.path
        code, err, out = self.executor.exec(
            f"git cherry-pick {shlex.quote(sha)}",
            cwd=path,
            flags=WAITING | REPLY | DECODE,
        )
        if code == 0:
            return
        if self.sequencer_in_progress(path) == "cherry-pick":
            # A nested pick errors before touching the tree; do not confuse
            # it with a genuine empty-result pause.
            if "already in progress" in (err or "").lower():
                raise GitError(err or "cherry-pick is already in progress")
            if self.has_unmerged_paths(path):
                raise SequencerPaused(
                    err or out or "Cherry-pick conflict",
                    reason="conflict",
                )
            raise SequencerPaused(
                err or out or "Cherry-pick empty",
                reason="empty",
            )
        raise GitError(err or out or f"Cherry-pick failed: {sha}")

    def commit_no_edit(self, path: str | None = None) -> None:
        """Complete a merge with the default message (``git commit --no-edit``)."""
        path = path or self.path
        code, err, _ = self.executor.exec(
            "git commit --no-edit",
            cwd=path,
            flags=WAITING | REPLY | DECODE,
        )
        if code != 0:
            msg = err or "Commit failed"
            raise GitError(msg)

    def amend_head(self, path: str | None = None) -> None:
        """Amend HEAD with staged changes, keeping the existing message."""
        path = path or self.path
        code, err, _ = self.executor.exec(
            ["git", "commit", "--amend", "--no-edit"],
            cwd=path,
            flags=WAITING | REPLY | DECODE,
        )
        if code != 0:
            msg = err or "Amend failed"
            raise GitError(msg)

    def commit(self, message: str, path: str | None = None) -> None:
        """Create a commit with the given message."""
        import tempfile

        path = path or self.path
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write(message)
            tmp_path = f.name
        try:
            code, err, _ = self.executor.exec(
                ["git", "commit", "-F", tmp_path],
                cwd=path,
                flags=WAITING | REPLY | DECODE,
            )
        finally:
            os.unlink(tmp_path)
        if code != 0:
            msg = err or "Commit failed"
            raise GitError(msg)
