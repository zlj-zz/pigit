# -*- coding: utf-8 -*-
"""
Module: pigit/observe/digest.py
Description: Worktree porcelain digest for content-change discovery.
Author: Zev
Date: 2026-08-20
"""

from __future__ import annotations

import hashlib


def hash_porcelain(text: str) -> str:
    """Return a stable hex digest of ``git status --porcelain`` text."""
    return hashlib.sha256(text.encode("utf-8", errors="surrogateescape")).hexdigest()
