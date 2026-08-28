"""
Module: pigit/git/api/_bisect.py
Description: Git bisect status and control (start/good/bad/reset).
Author: Zev
Date: 2026-08-28
"""

from __future__ import annotations

import re
import shlex
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from pigit.ext.executor import WAITING, REPLY, DECODE

from ._base import _OpsBase
from ._errors import GitError

_BAD_RE = re.compile(r"^# bad: \[([0-9a-f]+)\]", re.IGNORECASE)
_GOOD_RE = re.compile(r"^# good: \[([0-9a-f]+)\]", re.IGNORECASE)


@dataclass(frozen=True)
class BisectState:
    """Snapshot of an in-progress bisect session."""

    good_sha: str | None
    bad_sha: str | None
    current_head: str
    steps_remaining: int


class _BisectOps(_OpsBase):
    """``git bisect`` status and mutation; refs are resolved to absolute SHAs."""

    def __init__(self, api, core) -> None:
        super().__init__(api)
        self._core = core

    def bisect_status(self, path: str | None = None) -> BisectState | None:
        """Return bisect progress, or None when no session is active.

        Reads ``BISECT_LOG`` for the latest absolute good/bad SHAs, then
        ``git rev-list --count <good>..<bad>`` for the remaining interval size.
        """
        path = path or self.path
        try:
            git_dir = Path(self._core.get_git_dir(path))
        except GitError:
            return None
        log_path = git_dir / "BISECT_LOG"
        if not log_path.is_file():
            return None

        try:
            text = log_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None

        good_sha: str | None = None
        bad_sha: str | None = None
        for line in text.splitlines():
            m_bad = _BAD_RE.match(line)
            if m_bad:
                bad_sha = m_bad.group(1)
                continue
            m_good = _GOOD_RE.match(line)
            if m_good:
                good_sha = m_good.group(1)

        current_head = self._resolve_sha("HEAD", path)
        steps = 0
        if good_sha and bad_sha:
            try:
                steps = self._count_range(good_sha, bad_sha, path)
            except GitError:
                # Interval unresolvable (drifted log, odd SHAs): report the
                # session as in-progress with an unknown step count, not an error.
                steps = 0
        return BisectState(
            good_sha=good_sha,
            bad_sha=bad_sha,
            current_head=current_head,
            steps_remaining=steps,
        )

    def bisect_start(
        self,
        good_ref: str,
        bad_ref: str | None = None,
        path: str | None = None,
    ) -> None:
        """Start bisect with absolute SHAs for ``bad_ref`` (default HEAD) and ``good_ref``."""
        path = path or self.path
        good_sha = self._resolve_sha(good_ref, path)
        bad_sha = self._resolve_sha(bad_ref or "HEAD", path)
        code, err, _ = self.executor.exec(
            f"git bisect start {shlex.quote(bad_sha)} {shlex.quote(good_sha)}",
            flags=WAITING | REPLY | DECODE,
            cwd=path,
        )
        if code != 0:
            raise GitError(err or "Failed to start bisect")

    def bisect_mark_good(self, path: str | None = None) -> None:
        """Mark the current HEAD as good (resolved to an absolute SHA)."""
        path = path or self.path
        sha = self._resolve_sha("HEAD", path)
        self._run_mark("good", sha, path)

    def bisect_mark_bad(self, path: str | None = None) -> None:
        """Mark the current HEAD as bad (resolved to an absolute SHA)."""
        path = path or self.path
        sha = self._resolve_sha("HEAD", path)
        self._run_mark("bad", sha, path)

    def bisect_reset(self, path: str | None = None) -> None:
        """End the bisect session and return to the pre-bisect branch."""
        path = path or self.path
        code, err, _ = self.executor.exec(
            "git bisect reset",
            flags=WAITING | REPLY | DECODE,
            cwd=path,
        )
        if code != 0:
            raise GitError(err or "Failed to reset bisect")

    def _run_mark(self, kind: str, sha: str, path: str) -> None:
        code, err, _ = self.executor.exec(
            f"git bisect {kind} {shlex.quote(sha)}",
            flags=WAITING | REPLY | DECODE,
            cwd=path,
        )
        if code != 0:
            raise GitError(err or f"Failed to mark bisect {kind}")

    def _resolve_sha(self, ref: str, path: str | None) -> str:
        return self._core.verify_commitish(ref, path)

    def _count_range(self, good_sha: str, bad_sha: str, path: str | None) -> int:
        code, err, out = self.executor.exec(
            "git rev-list --count " f"{shlex.quote(good_sha)}..{shlex.quote(bad_sha)}",
            flags=WAITING | REPLY | DECODE,
            cwd=path,
        )
        if code != 0 or not out:
            raise GitError(err or "Failed to count bisect range")
        try:
            return int(cast(str, out).strip())
        except ValueError as exc:
            raise GitError(f"Invalid rev-list count: {out!r}") from exc
