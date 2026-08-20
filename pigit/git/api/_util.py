"""
Module: pigit/git/api/_util.py
Description: Shared helpers and regex constants for the git API submodules.
Author: Zev
Date: 2026-08-13
"""

from __future__ import annotations

import ast
import re

from ..model import File

# Git config / branch / commit parsing regexes (shared across submodules).
_RE_CONFIG_NEWLINE = re.compile(r"\r\n|\r|\n")
_RE_CONFIG_URL = re.compile(r"url\s=\s(.*)")
_RE_BRANCH_AHEAD = re.compile(r"ahead (\d+)")
_RE_BRANCH_BEHIND = re.compile(r"behind (\d+)")
_RE_COMMIT_TAG = re.compile(r"tag: ([^,\\]+)")
_SHA_RE = re.compile(r"^[0-9a-f]{7,40}")

# TTL (seconds) for the status cache in _status.py.
_LOAD_STATUS_CACHE_TTL = 0.3


def byte_str2str(text: str) -> str:
    """Decode a byte literal string (e.g. b'foo') to str.

    Args:
        text: A string that looks like a Python bytes literal.

    Returns:
        The decoded string, or the original text on failure.
    """
    try:
        return ast.literal_eval(text).decode("utf-8")
    except (ValueError, SyntaxError, UnicodeDecodeError):
        return text


def parse_numstat(
    text: str,
) -> tuple[list[tuple[str, int, int]], int, int]:
    """Parse ``git show/stash --numstat`` output into files and totals."""
    files: list[tuple[str, int, int]] = []
    total_add = 0
    total_del = 0
    for line in text.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        add = int(parts[0]) if parts[0].isdigit() else 0
        delete = int(parts[1]) if parts[1].isdigit() else 0
        files.append((parts[2], add, delete))
        total_add += add
        total_del += delete
    return files, total_add, total_del


def _file_path_for_cmd(file: File | str) -> str:
    if isinstance(file, File):
        return file.get_file_str()
    s = str(file)
    return s.split("->")[-1].strip() if "->" in s else s
