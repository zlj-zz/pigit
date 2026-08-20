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
from ._util import parse_numstat
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

    def stash_numstat(
        self, ref: str, path: str | None = None
    ) -> tuple[list[tuple[str, int, int]], int, int]:
        """Return numstat for a stash entry."""
        path = path or self.path
        _code, _err, resp = self.executor.exec(
            f"git stash show --numstat {shlex.quote(ref)}",
            flags=REPLY | DECODE,
            cwd=path,
        )
        if not resp:
            return [], 0, 0
        return parse_numstat(str(resp))

    def stash_meta(
        self, ref: str, path: str | None = None
    ) -> tuple[str, int, list[str]] | None:
        """Return ``(author, unix_ts, parent_shas)`` for a stash commit."""
        path = path or self.path
        _code, _err, out = self.executor.exec(
            f"git log -1 --format=%aN%x00%at%x00%P {shlex.quote(ref)}",
            flags=REPLY | DECODE,
            cwd=path,
        )
        text = str(out or "").strip()
        if not text:
            return None
        # NUL separators so a "|" in the author name cannot split them.
        author, ts_raw, parents_raw = text.split("\x00", 2)
        try:
            ts = int(ts_raw)
        except ValueError:
            return None
        parents = [p for p in parents_raw.split() if p]
        return author, ts, parents
