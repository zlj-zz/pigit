"""
Module: pigit/git/api/_commit.py
Description: Commit and log operations.
Author: Zev
Date: 2026-08-13
"""

from __future__ import annotations

import shlex
from collections.abc import Iterator
from typing import cast

from pigit.ext.executor import REPLY, DECODE

from ..model import Commit
from ._base import _OpsBase
from ._errors import GitError
from ._util import _RE_COMMIT_TAG

# Default pretty format for git log output (shared with the facade).
_DEFAULT_LOG_FORMAT = (
    '--oneline --pretty=format:"%H|%at|%aN|%d|%p|%s" --abbrev=20 --date=unix'
)

# Native `git log --decorate --graph` preview: bounded, no `--all`.
LOG_GRAPH_LIMIT = 80
_LOG_GRAPH_ARGS = "--decorate --graph --color=always"


class _CommitOps(_OpsBase):
    """Commit listing, log, and metadata."""

    def __init__(self, api, core) -> None:
        super().__init__(api)
        self._core = core

    def load_log(
        self,
        branch_name: str = "",
        limit: int | None = None,
        filter_path: str = "",
        arg_str: str = _DEFAULT_LOG_FORMAT,
        path: str | None = None,
    ) -> str:
        path = path or self.path

        branch_part = shlex.quote(branch_name) if branch_name else ""
        limit_part = f"-{limit}" if limit else ""
        filter_part = f"--follow -- {shlex.quote(filter_path)}" if filter_path else ""
        _, _, resp = self.executor.exec(
            f"git log {branch_part} {arg_str} {limit_part} {filter_part}",
            flags=REPLY | DECODE,
            cwd=path,
        )

        return "" if resp is None else cast(str, resp).strip()

    def load_log_graph(
        self,
        branch_name: str,
        limit: int = LOG_GRAPH_LIMIT,
        path: str | None = None,
    ) -> str:
        """Return native ``git log --decorate --graph`` text for ``branch_name``.

        Args:
            branch_name: Ref to log (``%(refname:short)``, e.g. ``origin/foo``).
            limit: Max commits (``git log -n``). Defaults to ``LOG_GRAPH_LIMIT``.
            path: Repo root; defaults to :attr:`path`.

        Returns:
            Stripped graph text, or empty string when ``branch_name`` is empty.

        Raises:
            GitError: ``git log`` failed (e.g. the ref no longer exists).
        """
        if not branch_name:
            return ""

        path = path or self.path
        code, err, resp = self.executor.exec(
            f"git log {_LOG_GRAPH_ARGS} -n {limit} {shlex.quote(branch_name)}",
            flags=REPLY | DECODE,
            cwd=path,
        )
        if code != 0:
            raise GitError(err or f"git log --graph failed for {branch_name}")
        return "" if resp is None else cast(str, resp).strip()

    def iter_commits(
        self,
        branch_name: str,
        limit: bool = True,
        max_commits: int = 300,
        filter_path: str = "",
        path: str | None = None,
    ) -> Iterator[Commit]:
        """Yield commits for ``branch_name`` while reading ``git log`` as a stream.

        Args:
            branch_name: Branch ref to log.
            limit: When True, cap at ``max_commits`` (``git log -n``).
            max_commits: Max entries when ``limit`` is True.
            filter_path: Optional path filter (``--follow``).
            path: Repo root; defaults to :attr:`path`.
        """
        path = path or self.path

        first_pushed_commit = self._core.get_first_pushed_commit(path, branch_name)
        passed_first_pushed_commit = not first_pushed_commit

        branch_part = shlex.quote(branch_name) if branch_name else ""
        limit_part = f"-n {max_commits}" if limit else ""
        filter_part = f"--follow -- {shlex.quote(filter_path)}" if filter_path else ""
        command = (
            f"git log {branch_part} --oneline "
            f'--pretty=format:"%H|%at|%aN|%d|%P|%s" '
            f"{limit_part} --abbrev=20 --date=unix {filter_part}"
        ).strip()

        for line in self.executor.exec_stream(command, cwd=path):
            if not line.strip():
                continue
            split_ = line.split("|")
            if len(split_) < 6:
                continue

            sha = split_[0]
            unix_timestamp = int(split_[1])
            author = split_[2]
            extra_info = (split_[3]).strip()
            parent_str = split_[4].strip()
            message = "|".join(split_[5:])

            parents = parent_str.split() if parent_str else []

            tag = []
            if extra_info:
                if match := _RE_COMMIT_TAG.search(extra_info):
                    tag.append(match[1])

            if sha == first_pushed_commit:
                passed_first_pushed_commit = True
            status = {True: "unpushed", False: "pushed"}[not passed_first_pushed_commit]

            yield Commit(
                sha=sha,
                msg=message,
                author=author,
                unix_timestamp=unix_timestamp,
                status=status,
                extra_info=extra_info,
                tag=tag,
                parents=parents,
            )

    def load_commits(
        self,
        branch_name: str,
        limit: bool = True,
        filter_path: str = "",
        path: str | None = None,
        max_commits: int = 300,
    ) -> list[Commit]:
        """Get commits for a branch (materializes :meth:`iter_commits`)."""
        return list(
            self.iter_commits(
                branch_name,
                limit=limit,
                max_commits=max_commits,
                filter_path=filter_path,
                path=path,
            )
        )

    def list_commits_in_range(self, base: str, path: str | None = None) -> list[Commit]:
        """Return commits in ``base..HEAD`` (oldest-first) with sha, parents, subject.

        Used to build the interactive-rebase todo list. Unlike :meth:`iter_commits`,
        this does not apply a ``-n`` cap or pushed/unpushed status logic, and it
        preserves ``--reverse`` order.
        """
        path = path or self.path
        cmd = (
            f'git log --reverse --topo-order --pretty=format:"%H|%P|%s" '
            f"{shlex.quote(base)}..HEAD"
        )
        code, err, resp = self.executor.exec(cmd, flags=REPLY | DECODE, cwd=path)
        if code != 0:
            raise GitError(err or f"git log failed for {base}")
        commits: list[Commit] = []
        if not resp:
            return commits
        for line in cast(str, resp).splitlines():
            if not line.strip():
                continue
            parts = line.split("|", 2)
            if len(parts) < 3:
                continue
            sha, parents_str, subject = parts
            parents = parents_str.split() if parents_str.strip() else []
            commits.append(
                Commit(
                    sha=sha,
                    msg=subject,
                    author="",
                    unix_timestamp=0,
                    status="",
                    extra_info="",
                    tag=[],
                    parents=parents,
                )
            )
        return commits

    def get_commit_bodies(
        self,
        branch_name: str,
        max_commits: int = 300,
        path: str | None = None,
    ) -> dict[str, str]:
        """Return a ``{sha: full body}`` map for ``branch_name``.

        ``%B`` in ``git log`` includes the subject and any extra lines from
        ``git commit -m`` separated by blank lines, so callers needing the
        full message must read it instead of ``%s``. Records are framed with
        ASCII RS (``\\x1e``) and SHA/body split with US (``\\x1f``) so multi-line
        bodies survive shell parsing without ambiguity.
        """
        path = path or self.path
        branch_part = shlex.quote(branch_name) if branch_name else ""
        cmd = (f"git log {branch_part} --format=%H%x1f%B%x1e -n {max_commits}").strip()
        _, _, resp = self.executor.exec(cmd, flags=REPLY | DECODE, cwd=path)

        bodies: dict[str, str] = {}
        if resp is None:
            return bodies
        resp_str = cast(str, resp)
        for record in resp_str.split("\x1e"):
            record = record.strip("\n")
            if not record or "\x1f" not in record:
                continue
            sha, body = record.split("\x1f", 1)
            bodies[sha.strip()] = body.strip("\n")
        return bodies

    def load_commit_info(
        self,
        commit_sha: str = "",
        file_name: str = "",
        plain: bool = False,
        path: str | None = None,
    ) -> str:
        """Gets the change of a file or all in a given commit.
        Args:
                commit_sha: commit id.
                file_name: file name(include full path).
                plain: whether has color.
        """
        path = path or self.path
        color_str = "never" if plain else "always"

        if file_name:
            cmd = f"git show --color={color_str} {shlex.quote(commit_sha)} -- {shlex.quote(file_name)}"
        else:
            cmd = f"git show --color={color_str} {shlex.quote(commit_sha)}"

        _, _, resp = self.executor.exec(
            cmd,
            flags=REPLY | DECODE,
            cwd=path,
        )
        if resp is None:
            return ""
        return cast(str, resp).rstrip()

    def get_commit_stats(
        self, commit_sha: str, path: str | None = None
    ) -> tuple[list[tuple[str, int, int]], int, int]:
        """Get changed files and insertion/deletion counts for a commit.

        Returns:
            (files, total_insertions, total_deletions) where files is a list
            of (file_name, insertions, deletions).
        """
        path = path or self.path
        _, _, resp = self.executor.exec(
            f"git show --numstat --format= {shlex.quote(commit_sha)}",
            flags=REPLY | DECODE,
            cwd=path,
        )
        if not resp:
            return [], 0, 0

        files: list[tuple[str, int, int]] = []
        total_add = 0
        total_del = 0

        resp_str = cast(str, resp)
        for line in resp_str.strip().splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) >= 3:
                add = int(parts[0]) if parts[0].isdigit() else 0
                delete = int(parts[1]) if parts[1].isdigit() else 0
                file_name = parts[2]
                files.append((file_name, add, delete))
                total_add += add
                total_del += delete

        return files, total_add, total_del
