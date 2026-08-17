"""
Module: pigit/git/api/_status.py
Description: Working-tree status loading.
Author: Zev
Date: 2026-08-13
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import cast

from pigit.ext.executor import SILENT, REPLY, DECODE

from ..model import File
from ._base import _OpsBase
from ._errors import RepoError
from ._util import byte_str2str, _LOAD_STATUS_CACHE_TTL


class _StatusOps(_OpsBase):
    """Working-tree status and staged-change checks."""

    def __init__(self, api, core) -> None:
        super().__init__(api)
        self._core = core

    def _load_status_cache_signature(
        self, cwd: str
    ) -> tuple[int, int, int, int, bool] | None:
        git_dir = self._core._find_dot_git_dir(cwd)
        if not git_dir:
            return None

        def st(p: "Path") -> tuple[int, int]:
            try:
                s = p.stat()
                return (s.st_mtime_ns, s.st_size)
            except OSError:
                return (0, 0)

        git = Path(git_dir)
        index_p = git / "index"
        head_p = git / "HEAD"
        merge = git / "MERGE_HEAD"
        i0, i1 = st(index_p)
        h0, h1 = st(head_p)
        return (i0, i1, h0, h1, merge.exists())

    def load_status(
        self,
        path: str | None = None,
        use_cache: bool = True,
    ) -> list[File]:
        """Get the file tree status of GIT for processing and encapsulation.

        Returns structured ``File`` objects; formatting and truncation are the
        caller's responsibility (e.g. the panel layer).

        Args:
                use_cache (bool): When True, reuse recent result if git metadata unchanged
                    and within a short TTL (see module constant ``_LOAD_STATUS_CACHE_TTL``).

        Returns:
                (list[File]): Processed file status list.
        """
        path = path or self.path
        if path is None or path == "":
            workdir = str(Path(".").resolve())
        else:
            workdir = str(Path(path).resolve())

        key = (workdir,)
        now = time.monotonic()
        cache_sig = self._load_status_cache_signature(workdir) if use_cache else None

        if use_cache and cache_sig is not None:
            c = getattr(self, "_load_status_cache", None)
            if (
                c
                and c["key"] == key
                and c["sig"] == cache_sig
                and (now - c["time"] < _LOAD_STATUS_CACHE_TTL)
            ):
                return c["files"]

        file_items = []

        _, err, files = self.executor.exec(
            "git status -s -u --porcelain", flags=REPLY | DECODE, cwd=workdir
        )
        if err or files is None:
            return file_items
        for file in cast(str, files).rstrip().splitlines():
            if not file.strip():
                # skip blank line.
                continue

            change = file[:2]
            staged_change = file[:1]
            unstaged_change = file[1:2]
            name = file[3:]
            if name.endswith('"'):
                # may is chinese char code.
                name = byte_str2str(name[1:-1])
            untracked = change == "??"
            has_no_staged_change = staged_change in [" ", "U", "?"]
            has_merged_conflicts = change in ["DD", "AA", "UU", "AU", "UA", "UD", "DU"]
            has_inline_merged_conflicts = change in ["UU", "AA"]

            file_ = File(
                name=name,
                display_str=name,
                short_status=change,
                has_staged_change=not has_no_staged_change,
                has_unstaged_change=unstaged_change != " ",
                tracked=not untracked,
                deleted=unstaged_change == "D" or staged_change == "D",
                added=unstaged_change == "A" or untracked,
                has_merged_conflicts=has_merged_conflicts,
                has_inline_merged_conflicts=has_inline_merged_conflicts,
            )

            file_items.append(file_)

        if use_cache and cache_sig is not None:
            self._load_status_cache = {
                "key": key,
                "sig": cache_sig,
                "time": now,
                "files": file_items,
            }
        return file_items

    def has_staged_changes(self, path: str | None = None) -> bool:
        """Return True if index has staged changes."""
        path = path or self.path
        code, _, _ = self.executor.exec(
            "git diff --cached --quiet", flags=REPLY | SILENT, cwd=path
        )
        # --quiet: exit 0 = no differences, 1 = differences exist
        if code == 0:
            return False
        if code == 1:
            return True
        raise RepoError(f"git diff --cached failed with exit code {code}")

    def has_unstaged_changes(self, path: str | None = None) -> bool:
        """Return True if the working tree has unstaged changes."""
        path = path or self.path
        code, _, _ = self.executor.exec(
            "git diff --quiet", flags=REPLY | SILENT, cwd=path
        )
        if code == 0:
            return False
        if code == 1:
            return True
        raise RepoError(f"git diff failed with exit code {code}")

    def has_untracked_changes(self, path: str | None = None) -> bool:
        """Return True if the working tree has untracked (non-ignored) files."""
        path = path or self.path
        code, _, out = self.executor.exec(
            "git ls-files --others --exclude-standard",
            flags=REPLY | DECODE,
            cwd=path,
        )
        if code == 0:
            return bool(out and out.strip())
        raise RepoError(f"git ls-files failed with exit code {code}")
