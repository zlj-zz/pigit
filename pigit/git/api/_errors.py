"""
Module: pigit/git/api/_errors.py
Description: Exception types raised by the git API.
Author: Zev
Date: 2026-08-13
"""

from __future__ import annotations

from typing import Literal


class RepoError(Exception):
    """Error class of ~GitOption."""


class GitError(Exception):
    """Raised when a git command fails."""


class SequencerPaused(GitError):
    """Cherry-pick (or similar) stopped with CHERRY_PICK_HEAD present."""

    def __init__(self, message: str, *, reason: Literal["conflict", "empty"]) -> None:
        super().__init__(message)
        self.reason = reason
