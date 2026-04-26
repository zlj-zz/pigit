# -*- coding: utf-8 -*-
"""
Module: pigit/git/cmds/_completion_types.py
Description: Completion types for git argument completion.
Author: Zev
Date: 2026-04-15
"""

from enum import Enum


class CompletionType(Enum):
    """Parameter completion types for shell completion and picker argument prompting."""

    NONE = ""  # No special completion
    BRANCH = "branch"  # Git branch names
    FILE = "file"  # File paths (git tracked/untracked)
    REMOTE = "remote"  # Remote names
    TAG = "tag"  # Tag names
    COMMIT = "commit"  # Commit hashes
    STASH = "stash"  # Stash entries
    REF = "ref"  # Any git ref (branch/tag/commit)
