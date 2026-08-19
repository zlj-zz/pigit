"""
Module: pigit/git/api/_stash.py
Description: Stash listing and mutation.
Author: Zev
Date: 2026-08-13
"""

from __future__ import annotations

import shlex

from pigit.ext.executor import WAITING, REPLY, DECODE

from ..model import Stash
from ._base import _OpsBase
from ._errors import GitError


class _StashOps(_OpsBase):
    """Stash listing, push, apply/pop/drop, and diff."""

    def __init__(self, api) -> None:
        super().__init__(api)

    def load_stashes(
        self,
        path: str | None = None,
    ) -> list[Stash]:
        """Load stash entries.

        Args:
            path: Repository path. Uses ``self.path`` if None.

        Returns:
            List of Stash objects ordered newest first.
        """
        path = path or self.path
        _, err, resp = self.executor.exec(
            'git stash list --format="%gd|%h|%s"',
            flags=REPLY | DECODE,
            cwd=path,
        )
        if err or resp is None:
            return []
        assert isinstance(resp, str)
        text = resp
        stashes: list[Stash] = []
        for line in text.strip().splitlines():
            parts = line.split("|", 2)
            if len(parts) >= 3:
                stashes.append(Stash(ref=parts[0], sha=parts[1], msg=parts[2]))
        return stashes

    def stash_push(
        self,
        path: str | None = None,
        message: str = "",
    ) -> None:
        """Stash tracked and untracked changes (``git stash push -u``).

        Args:
            path: Repository path.
            message: Optional stash message.

        Raises:
            GitError: If the stash command fails.
        """
        path = path or self.path
        cmd = "git stash push -u"
        if message:
            cmd += f" -m {shlex.quote(message)}"
        code, err, _ = self.executor.exec(
            cmd,
            flags=WAITING | REPLY | DECODE,
            cwd=path,
        )
        if code != 0:
            raise GitError(err or "Stash failed")

    def _run_ref_action(
        self,
        action: str,
        ref: str,
        path: str | None,
    ) -> None:
        """Run ``git stash <action> <ref>`` and raise GitError on failure."""
        path = path or self.path
        code, err, _ = self.executor.exec(
            f"git stash {action} {shlex.quote(ref)}",
            flags=WAITING | REPLY | DECODE,
            cwd=path,
        )
        if code != 0:
            raise GitError(err or f"{action.capitalize()} failed: {ref}")

    def stash_pop(
        self,
        ref: str,
        path: str | None = None,
    ) -> None:
        """Pop a stash entry (apply then drop)."""
        self._run_ref_action("pop", ref, path)

    def stash_apply(
        self,
        ref: str,
        path: str | None = None,
    ) -> None:
        """Apply a stash entry without dropping it."""
        self._run_ref_action("apply", ref, path)

    def stash_drop(
        self,
        ref: str,
        path: str | None = None,
    ) -> None:
        """Drop a stash entry."""
        self._run_ref_action("drop", ref, path)

    def load_stash_diff(
        self,
        ref: str,
        path: str | None = None,
    ) -> str:
        """Load the diff content of a stash entry.

        Args:
            ref: Stash reference (e.g. "stash@{0}").
            path: Repository path.

        Returns:
            Diff text as a single string.
        """
        path = path or self.path
        _, err, resp = self.executor.exec(
            f"git stash show -p {shlex.quote(ref)}",
            flags=REPLY | DECODE,
            cwd=path,
        )
        if err or resp is None:
            return ""
        assert isinstance(resp, str)
        return resp

    def stash_store(self, sha: str, path: str | None = None) -> None:
        """Store a commit as a stash entry."""
        path = path or self.path
        code, err, _ = self.executor.exec(
            f"git stash store {shlex.quote(sha)}",
            cwd=path,
            flags=WAITING | REPLY | DECODE,
        )
        if code != 0:
            raise GitError(err or f"stash store failed: {sha}")
