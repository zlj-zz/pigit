"""
Module: pigit/git/api/_errors.py
Description: Exception types raised by the git API.
Author: Zev
Date: 2026-08-13
"""

from __future__ import annotations


class RepoError(Exception):
    """Error class of ~GitOption."""


class GitError(Exception):
    """Raised when a git command fails."""
