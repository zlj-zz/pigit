"""
Module: pigit/git/api/_diff.py
Description: Diff loading and file history.
Author: Zev
Date: 2026-08-13
"""

from __future__ import annotations

import re
import shlex
from pathlib import Path
from typing import cast

from pigit.ext.executor import REPLY, DECODE

from ._base import _OpsBase
from ._util import _SHA_RE

# ``index <old>..<new>`` header: hashes are variable-length abbreviated hex.
_INDEX_HASH_RE = re.compile(r"^index ([0-9a-f]+)\.\.([0-9a-f]+)")


def parse_index_hashes(line: str) -> tuple[str | None, str | None] | None:
    """Parse ``index <old>..<new>`` blob hashes from a diff header line.

    Hashes are variable-length abbreviated hex (7+ chars). A missing side
    (all-zero ``0000000``) maps to ``None``. Returns ``None`` when *line*
    carries no ``index`` header.
    """
    m = _INDEX_HASH_RE.match(line)
    if not m:
        return None
    old_sha = None if set(m.group(1)) == {"0"} else m.group(1)
    new_sha = None if set(m.group(2)) == {"0"} else m.group(2)
    return old_sha, new_sha


class _DiffOps(_OpsBase):
    """Diff and per-file history."""

    def __init__(self, api) -> None:
        super().__init__(api)

    def load_file_diff(
        self,
        file: str,
        tracked: bool = True,
        cached: bool = False,
        plain: bool = False,
        path: str | None = None,
    ) -> str:
        """Gets the modification of the file.

        Args:
                file (str): file path relative to git.
                tracked (bool, optional): Defaults to True.
                cached (bool, optional): Defaults to False.
                plain (bool, optional): Whether need color. Defaults to False.

        Returns:
                (str): change string.
        """
        path = path or self.path

        _plain = "--color=never" if plain else "--color=always"
        _cached = "--cached" if cached else ""
        _tracked = "--" if tracked else "--no-index -- /dev/null"

        if "->" in file:  # rename status.
            file = file.split("->")[-1].strip()

        _, err, res = self.executor.exec(
            f"git diff --submodule --no-ext-diff {_plain} {_cached} {_tracked} "
            f"{shlex.quote(file)}",
            flags=REPLY | DECODE,
            cwd=path,
        )
        if err or res is None:
            return "Can't get diff."
        return cast(str, res).rstrip()

    def get_file_history(
        self, path: str, repo_path: str | None = None
    ) -> list[tuple[str, str]]:
        """Return [(sha, subject), ...] for all commits that touched *path*.

        Uses ``--follow --first-parent`` to track renames and produce a linear
        history compatible with p/n navigation. Non-first-parent branches are
        collapsed; this is a deliberate UX simplification.
        """
        repo_path = repo_path or self.path
        code, err, out = self.executor.exec(
            f"git log --follow --first-parent --oneline -- {shlex.quote(path)}",
            flags=REPLY | DECODE,
            cwd=repo_path,
        )
        if code != 0:
            self.log.warning("git log --follow failed: %s", err)
            return []
        lines = cast(str, out).strip().splitlines() if out else []
        commits: list[tuple[str, str]] = []
        for line in lines:
            if _SHA_RE.match(line) and " " in line:
                sha, subject = line.split(" ", 1)
                commits.append((sha, subject))
        return commits

    def get_file_at_commit(
        self,
        commit_sha: str,
        path: str,
        repo_path: str | None = None,
        max_size: int = 1_048_576,
    ) -> str | None:
        """Return file content at *commit_sha*, or ``None`` if deleted.

        Returns a sentinel string ``"\\x00BINARY_OR_TOO_LARGE:size\\x00"``
        for binary or oversized files so the renderer can show a message.
        """
        repo_path = repo_path or self.path

        # 1. Check size first to avoid loading multi-MB files into memory
        size_code, _, size_out = self.executor.exec(
            f"git cat-file -s {shlex.quote(commit_sha)}:{shlex.quote(path)}",
            flags=REPLY | DECODE,
            cwd=repo_path,
        )
        if size_code != 0:
            return None  # File does not exist at this commit
        try:
            size = int(cast(str, size_out).strip())
        except ValueError:
            size = -1
        if size > max_size:
            return f"\x00BINARY_OR_TOO_LARGE:{size}\x00"

        # 2. Fetch content
        code, err, out = self.executor.exec(
            f"git show {shlex.quote(commit_sha)}:{shlex.quote(path)}",
            flags=REPLY | DECODE,
            cwd=repo_path,
        )
        if code != 0:
            self.log.warning("git show failed: %s", err)
            return None
        if out is None:
            return ""

        raw = cast(str, out).encode("utf-8") if isinstance(out, str) else out
        if b"\x00" in raw[:8192]:
            return f"\x00BINARY_OR_TOO_LARGE:{size}\x00"

        return (
            cast(str, out)
            if isinstance(out, str)
            else out.decode("utf-8", errors="replace")
        )

    def load_blob(
        self,
        sha: str,
        repo_path: str | None = None,
        max_size: int = 1_048_576,
    ) -> list[str] | None:
        """Return blob content lines by object hash, or ``None``.

        Mirrors the :meth:`get_file_at_commit` protections (size cap via
        ``cat-file -s``, then binary skip) but returns ``None`` instead of a
        sentinel: the diff highlighter simply falls back when a side cannot
        be loaded.

        Args:
            sha: Blob hash (abbreviated hashes are accepted by git).
            repo_path: Repository root; defaults to ``self.path``.
            max_size: Size cap in bytes.

        Returns:
            Content split into lines, or ``None`` for missing/oversized/binary.
        """
        repo_path = repo_path or self.path
        size_code, _, size_out = self.executor.exec(
            f"git cat-file -s {shlex.quote(sha)}",
            flags=REPLY | DECODE,
            cwd=repo_path,
        )
        if size_code != 0:
            return None  # object not in this repository's store
        try:
            size = int(cast(str, size_out).strip())
        except ValueError:
            return None
        if size > max_size:
            return None

        code, err, out = self.executor.exec(
            f"git cat-file blob {shlex.quote(sha)}",
            flags=REPLY | DECODE,
            cwd=repo_path,
        )
        if code != 0:
            # Missing objects are the normal case for the worktree side of an
            # unstaged diff (its blob is never stored); log at debug level.
            self.log.debug("git cat-file blob failed: %s", err)
            return None
        if out is None:
            return []
        raw = cast(str, out).encode("utf-8") if isinstance(out, str) else out
        if b"\x00" in raw[:8192]:
            return None  # binary
        text = (
            cast(str, out)
            if isinstance(out, str)
            else out.decode("utf-8", errors="replace")
        )
        return text.splitlines()

    def load_worktree_file(
        self,
        path: str,
        repo_path: str | None = None,
        max_size: int = 1_048_576,
    ) -> list[str] | None:
        """Read a worktree file from disk (uncommitted new-side source).

        Args:
            path: Repo-relative file path.
            repo_path: Repository root; defaults to ``self.path``.
            max_size: Size cap in bytes.

        Returns:
            Content split into lines, or ``None`` when
            missing/oversized/binary.
        """
        repo_path = repo_path or self.path
        file_path = Path(repo_path) / path
        try:
            if file_path.stat().st_size > max_size:
                return None
            raw = file_path.read_bytes()
        except OSError:
            return None
        if b"\x00" in raw[:8192]:
            return None  # binary
        return raw.decode("utf-8", errors="replace").splitlines()
