"""
Module: pigit/git/api/_branch.py
Description: Branch listing and mutation operations.
Author: Zev
Date: 2026-08-13
"""

from __future__ import annotations

import shlex
import time
from typing import cast

from pigit.ext.executor import WAITING, REPLY, DECODE

from ..model import Branch, ReflogEntry
from ._base import _OpsBase
from ._errors import GitError
from ._util import _RE_BRANCH_AHEAD, _RE_BRANCH_BEHIND


class _BranchOps(_OpsBase):
    """Branch listing and mutation."""

    def __init__(self, api) -> None:
        super().__init__(api)

    def get_branches(
        self,
        path: str | None = None,
        include_remote: bool = False,
        plain: bool = True,
    ) -> list[str]:
        """Get repo all branch."""
        path = path or self.path

        include_all = "--all" if include_remote else ""
        color = "never" if plain else "always"

        _, _, res = self.executor.exec(
            f"git branch {include_all} --color={color}",
            flags=REPLY | DECODE,
            cwd=path,
        )

        if res is None:
            return []
        return [branch[2:] for branch in cast(str, res).rstrip().splitlines()]

    def load_branches(
        self,
        path: str | None = None,
        *,
        scope: str = "local",
    ) -> list[Branch]:
        path = path or self.path
        branches: list[Branch] = []

        if scope == "remote":
            flag = "-r"
        elif scope == "all":
            flag = "-a"
        else:
            flag = ""

        _, _, resp = self.executor.exec(
            f"git branch {flag} --sort=-committerdate "
            '--format="%(HEAD)|%(refname:short)|%(refname)|%(upstream:short)|%(upstream:track)" ',
            flags=REPLY | DECODE,
            cwd=path,
        )
        if resp is None:
            return branches
        resp = cast(str, resp).strip()
        if not resp:
            return branches

        for line in resp.splitlines():
            items = line.split("|")
            short_name = cast(str, items[1])
            full_ref = cast(str, items[2])
            is_remote = full_ref.startswith("refs/remotes/")

            # Skip the symbolic HEAD ref for remotes (e.g. origin/HEAD)
            if is_remote and short_name.endswith("/HEAD"):
                continue

            branch = Branch(
                name=short_name,
                ahead="?",
                behind="?",
                is_head=items[0] == "*" and not is_remote,
                is_remote=is_remote,
            )

            upstream_name = items[3]

            if not upstream_name or is_remote:
                branches.append(branch)
                continue

            branch.upstream_name = cast(str, upstream_name)

            track = items[4]
            branch.ahead = (
                str(m[1]) if (m := _RE_BRANCH_AHEAD.search(cast(str, track))) else "0"
            )
            branch.behind = (
                str(m[1]) if (m := _RE_BRANCH_BEHIND.search(cast(str, track))) else "0"
            )
            branches.append(branch)

        return branches

    def checkout_branch(self, branch_name: str, path: str | None = None) -> None:
        path = path or self.path
        code, err, out = self.executor.exec(
            f"git checkout {shlex.quote(branch_name)}",
            cwd=path,
            flags=WAITING | REPLY | DECODE,
        )
        if code != 0:
            raise GitError(err or f"checkout failed: {branch_name}")

    def rename_branch(
        self,
        old_name: str,
        new_name: str,
        path: str | None = None,
    ) -> None:
        path = path or self.path
        code, err, out = self.executor.exec(
            f"git branch -m {shlex.quote(old_name)} {shlex.quote(new_name)}",
            cwd=path,
            flags=WAITING | REPLY | DECODE,
        )
        if code != 0:
            raise GitError(err or f"rename failed: {old_name} -> {new_name}")

    def create_branch(
        self,
        branch_name: str,
        path: str | None = None,
    ) -> None:
        """Create a new branch from HEAD and switch to it."""
        path = path or self.path
        code, err, out = self.executor.exec(
            f"git checkout -b {shlex.quote(branch_name)}",
            cwd=path,
            flags=WAITING | REPLY | DECODE,
        )
        if code != 0:
            raise GitError(err or f"create branch failed: {branch_name}")

    def delete_branch(
        self,
        branch_name: str,
        force: bool = False,
        path: str | None = None,
    ) -> None:
        """Delete a local branch."""
        path = path or self.path
        flag = "-D" if force else "-d"
        code, err, out = self.executor.exec(
            f"git branch {flag} {shlex.quote(branch_name)}",
            cwd=path,
            flags=WAITING | REPLY | DECODE,
        )
        if code != 0:
            raise GitError(err or f"delete branch failed: {branch_name}")

    def create_branch_at(
        self, branch_name: str, sha: str, path: str | None = None
    ) -> None:
        """Create a branch at a specific commit."""
        path = path or self.path
        code, err, _ = self.executor.exec(
            f"git branch {shlex.quote(branch_name)} {shlex.quote(sha)}",
            cwd=path,
            flags=WAITING | REPLY | DECODE,
        )
        if code != 0:
            raise GitError(err or f"create branch at {sha} failed: {branch_name}")

    def _branch_sha(self, branch_name: str, path: str | None = None) -> str | None:
        """Get the SHA of a branch. Returns None if the branch does not exist."""
        path = path or self.path
        code, _err, out = self.executor.exec(
            f"git rev-parse --verify {shlex.quote(branch_name)}",
            cwd=path,
            flags=REPLY | DECODE,
        )
        if code != 0 or not out:
            return None
        return cast(str, out).strip()

    def get_branch_creation_time(
        self, branch_name: str, path: str | None = None
    ) -> str:
        """Return branch creation date as YYYY-MM-DD (best-effort via reflog)."""
        path = path or self.path
        _, _, resp = self.executor.exec(
            f"git reflog show {shlex.quote(branch_name)} --format=%at | tail -1",
            flags=REPLY | DECODE,
            cwd=path,
            shell=True,
        )
        if not resp:
            return "?"
        try:
            ts = int(resp.strip())
            return time.strftime("%Y-%m-%d", time.localtime(ts))
        except ValueError:
            return "?"

    def list_reflog(
        self, limit: int = 50, path: str | None = None
    ) -> list[ReflogEntry]:
        """Return the newest ``limit`` HEAD reflog entries (newest first).

        Parses ``git reflog -n <limit> --format=%H%x09%gD%x09%gs%x09%at``:
        full sha / ``HEAD@{n}`` / reflog message / unix seconds. The reflog
        message may itself contain tabs, so each line is split at most three
        times to keep the message whole. An empty reflog returns ``[]``.

        Args:
            limit: How many most-recent entries to fetch.
            path: Repo path; defaults to ``self.path``.

        Returns:
            Parsed entries, newest first.
        """
        path = path or self.path
        _code, _err, out = self.executor.exec(
            f"git reflog -n {limit} --format=%H%x09%gD%x09%gs%x09%at",
            flags=REPLY | DECODE,
            cwd=path,
        )
        if not out:
            return []
        entries: list[ReflogEntry] = []
        for line in out.splitlines():
            # ``when`` is always the final tab field; split it off first so a
            # tab inside %gs cannot shift it, then split the head at most
            # twice to keep the message whole.
            head, _, when = line.rpartition("\t")
            fields = head.split("\t", 2)
            if len(fields) < 3:
                continue
            sha, refish, message = fields
            try:
                entries.append(ReflogEntry(sha, refish, message, int(when)))
            except ValueError:
                continue
        return entries

    def get_branch_recent_commit(
        self, branch_name: str, path: str | None = None
    ) -> tuple[str, str]:
        """Return ``(subject, author)`` of the branch tip commit.

        Both values are ``"?"`` when the branch has no commits.

        Args:
            branch_name: Branch or remote-tracking name to log.
            path: Repo path; defaults to ``self.path``.

        Returns:
            ``(subject, author)``.
        """
        path = path or self.path
        _code, _err, out = self.executor.exec(
            f"git log {shlex.quote(branch_name)} -1 --pretty=format:%s%x00%aN",
            flags=REPLY | DECODE,
            cwd=path,
        )
        text = (out or "").strip()
        if not text:
            return "?", "?"
        # NUL separates subject and author so a "|" in either cannot split them.
        subject, _sep, author = text.partition("\x00")
        return subject, author or "?"
