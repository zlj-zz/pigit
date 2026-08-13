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


def _file_path_for_cmd(file: File | str) -> str:
    if isinstance(file, File):
        return file.get_file_str()
    s = str(file)
    return s.split("->")[-1].strip() if "->" in s else s
