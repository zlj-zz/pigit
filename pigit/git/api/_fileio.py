"""
Module: pigit/git/api/_fileio.py
Description: File IO and git object primitives (session-history support).
Author: Zev
Date: 2026-08-13
"""

from __future__ import annotations

import shlex
import time
from pathlib import Path
from typing import cast

from pigit.ext.executor import REPLY, DECODE

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
        """Get file size and last modification time as formatted strings.

        Returns:
            (size_str, mtime_str) like ("12.5K", "2026-04-24 10:30").
        """
        path = path or self.path
        if path is None:
            return "", ""
        file_name = _file_path_for_cmd(file)
        file_path = Path(path) / file_name
        try:
            st = file_path.stat()
            size = self._format_size(st.st_size)
            mtime = time.strftime("%Y-%m-%d %H:%M", time.localtime(st.st_mtime))
            return size, mtime
        except OSError:
            return "?", "?"

    @staticmethod
    def _format_size(size: int) -> str:
        if size < 1024:
            return f"{size}B"
        if size < 1024 * 1024:
            return f"{size / 1024:.1f}K"
        return f"{size / (1024 * 1024):.1f}M"
