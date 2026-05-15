"""
Module: pigit/git/_repo_status.py
Description: Shared repo status helpers for picker widgets.
Author: Zev
Date: 2026-05-16
"""

from __future__ import annotations

import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import NamedTuple
from collections.abc import Sequence

from pigit.termui._picker import PickerRow


class RepoStatus(NamedTuple):
    """Git status summary for a repository."""

    branch: str
    has_unstaged: bool
    has_staged: bool
    has_untracked: bool

    @property
    def symbols(self) -> str:
        """Return compact status symbols (* unstaged, + staged, ? untracked)."""
        return (
            ("*" if self.has_unstaged else "")
            + ("+" if self.has_staged else "")
            + ("?" if self.has_untracked else "")
        )


def _git_output(args: list[str]) -> str | None:
    """Run a git command and return stdout, or None on failure."""
    try:
        return subprocess.check_output(args, text=True, stderr=subprocess.DEVNULL).strip()
    except (subprocess.CalledProcessError, OSError):
        return None


def get_repo_status(path: str) -> RepoStatus:
    """Return branch and status for a repo path."""
    branch = _git_output(["git", "-C", path, "branch", "--show-current"]) or ""
    status_out = _git_output(["git", "-C", path, "status", "--short"])
    if status_out is None:
        return RepoStatus(branch, False, False, False)

    has_unstaged = False
    has_staged = False
    has_untracked = False
    for line in status_out.splitlines():
        if not line:
            continue
        xy = line[:2]
        if "?" in xy:
            has_untracked = True
            continue
        if xy[0] != " ":
            has_staged = True
        if xy[1] != " ":
            has_unstaged = True

    return RepoStatus(branch, has_unstaged, has_staged, has_untracked)


def query_repos_status(rows: Sequence[PickerRow]) -> dict[str, RepoStatus]:
    """Parallel status query for all repos."""
    results: dict[str, RepoStatus] = {}
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {
            pool.submit(get_repo_status, row.ref if isinstance(row.ref, str) else ""): row.title
            for row in rows
        }
        for future in as_completed(futures):
            name = futures[future]
            try:
                status = future.result()
            except Exception:
                status = RepoStatus("", False, False, False)
            results[name] = status
    return results
