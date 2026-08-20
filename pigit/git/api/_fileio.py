"""
Module: pigit/git/api/_fileio.py
Description: File IO and git object primitives (session-history support).
Author: Zev
Date: 2026-08-13
"""

from __future__ import annotations

import shlex
from pathlib import Path
from typing import cast

from pigit.ext.executor import WAITING, REPLY, DECODE

from ._base import _OpsBase
from ._errors import GitError
from ._util import _file_path_for_cmd


class _FileioOps(_OpsBase):
    """File IO and git object primitives."""

    def __init__(self, api) -> None:
        super().__init__(api)

    def hash_object_file(self, file, path: str | None = None) -> str | None:
        """git hash-object -w <file>. Returns SHA or None. Writes blob to object DB."""
        path = path or self.path
        file_name = _file_path_for_cmd(file)
        code, _err, out = self.executor.exec(
            f"git hash-object -w -- {shlex.quote(file_name)}",
            cwd=path,
            flags=REPLY | DECODE,
        )
        if code != 0 or not out:
            return None
        return cast(str, out).strip()

    def cat_file_to_path(self, sha: str, dest, path: str | None = None) -> None:
        """git cat-file -p <sha> > <dest>. Restores exact blob content."""
        path = path or self.path
        dest_name = _file_path_for_cmd(dest)
        code, err, out = self.executor.exec(
            f"git cat-file -p {shlex.quote(sha)}",
            cwd=path,
            flags=REPLY,
        )
        if code != 0:
            raise GitError(err or f"cat-file failed: {sha}")
        dest_path = Path(path or ".") / dest_name
        dest_path.write_bytes(
            out if isinstance(out, bytes) else cast(str, out).encode("utf-8")
        )

    def read_file_bytes(self, file, path: str | None = None) -> bytes | None:
        """Read raw file content."""
        path = path or self.path
        file_name = _file_path_for_cmd(file)
        file_path = Path(path or ".") / file_name
        try:
            return file_path.read_bytes()
        except OSError:
            return None

    def write_file_bytes(self, file, data: bytes, path: str | None = None) -> None:
        """Write raw bytes to file."""
        path = path or self.path
        file_name = _file_path_for_cmd(file)
        file_path = Path(path or ".") / file_name
        file_path.write_bytes(data)

    def get_file_info(self, file, path: str | None = None) -> tuple[str, str]:
        """Get file size and permission mode as formatted strings.

        Returns:
            (size_str, mode_str) like ("12.5K", "644"). Missing files are ("?", "?").
        """
        path = path or self.path
        if path is None:
            return "", ""
        file_name = _file_path_for_cmd(file)
        file_path = Path(path) / file_name
        try:
            st = file_path.stat()
            size = self._format_size(st.st_size)
            mode = f"{st.st_mode & 0o777:o}"
            return size, mode
        except OSError:
            return "?", "?"

    def compare_index_worktree(self, relpath: str, path: str | None = None) -> str:
        """Return ``equal``, ``differ``, or ``worktree`` (untracked)."""
        path = path or self.path
        quoted = shlex.quote(relpath)
        code, _err, _out = self.executor.exec(
            f"git rev-parse --verify --end-of-options :{quoted}",
            cwd=path,
            flags=WAITING | REPLY | DECODE,
        )
        if code != 0:
            # No stage-0 entry: the path is untracked, staged for deletion,
            # or in conflict. Only a genuinely untracked file is "worktree";
            # the others still have tracked/conflict state worth reporting.
            _ucode, _uerr, uout = self.executor.exec(
                f"git ls-files -u -- {quoted}",
                cwd=path,
                flags=REPLY | DECODE,
            )
            if (uout or "").strip():
                return "differ"  # unmerged
            hcode, _herr, _hout = self.executor.exec(
                f"git rev-parse --verify --end-of-options HEAD:{quoted}",
                cwd=path,
                flags=WAITING | REPLY | DECODE,
            )
            return "differ" if hcode == 0 else "worktree"
        # ``git diff --quiet`` applies the clean filter (EOL normalization,
        # ident, .gitattributes) to the worktree side, so it agrees with
        # ``git status`` where hashing the raw worktree bytes would not.
        code, _err, _out = self.executor.exec(
            f"git diff --quiet --no-ext-diff -- {quoted}",
            cwd=path,
            flags=WAITING | REPLY | DECODE,
        )
        return "equal" if code == 0 else "differ"

    def unmerged_stages(self, relpath: str, path: str | None = None) -> list[int]:
        """Return unique sorted index stages for an unmerged path."""
        path = path or self.path
        _code, _err, out = self.executor.exec(
            f"git ls-files -u -- {shlex.quote(relpath)}",
            cwd=path,
            flags=REPLY | DECODE,
        )
        stages: set[int] = set()
        for line in cast(str, out or "").splitlines():
            meta, _sep, _name = line.partition("\t")
            parts = meta.split()
            if len(parts) >= 3 and parts[2].isdigit():
                stages.add(int(parts[2]))
        return sorted(stages)

    def last_commit_for_path(
        self, relpath: str, path: str | None = None
    ) -> tuple[str, str, str, int] | None:
        """Return ``(short_sha, subject, author, unix_ts)`` for the last commit on *relpath*."""
        path = path or self.path
        _code, _err, out = self.executor.exec(
            f"git log -1 --format=%h%x00%s%x00%aN%x00%at -- {shlex.quote(relpath)}",
            cwd=path,
            flags=REPLY | DECODE,
        )
        text = cast(str, out or "").strip()
        if not text:
            return None
        # NUL separators so a "|" in the subject or author cannot split them.
        sha, subject, author, ts_raw = text.split("\x00", 3)
        try:
            ts = int(ts_raw)
        except ValueError:
            return None
        return sha, subject, author, ts

    @staticmethod
    def _format_size(size: int) -> str:
        if size < 1024:
            return f"{size}B"
        if size < 1024 * 1024:
            return f"{size / 1024:.1f}K"
        return f"{size / (1024 * 1024):.1f}M"
