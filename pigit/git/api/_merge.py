"""
Module: pigit/git/api/_merge.py
Description: Merge, pull, and commit operations.
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
from ._errors import GitError


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

    def is_merge_in_progress(self, path: str | None = None) -> bool:
        """Return True if MERGE_HEAD exists in the git directory."""
        try:
            git_dir = self._core.get_git_dir(path)
        except GitError:
            return False
        return (Path(git_dir) / "MERGE_HEAD").exists()

    def is_rebase_in_progress(self, path: str | None = None) -> bool:
        """Return True if a rebase is in progress (rebase-merge or rebase-apply dir)."""
        try:
            git_dir = self._core.get_git_dir(path)
        except GitError:
            return False
        return (Path(git_dir) / "rebase-merge").exists() or (
            Path(git_dir) / "rebase-apply"
        ).exists()

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
