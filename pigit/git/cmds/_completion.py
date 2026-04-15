# -*- coding: utf-8 -*-
"""
Module: pigit/git/cmds/_completion.py
Description: Git completion data source for picker argument prompting.
Author: Zev
Date: 2026-04-15
"""

import subprocess
from typing import Optional

from ._completion_types import CompletionType


def _git_run_text(args: list[str]) -> str:
    """Run a git command and return its stdout text."""
    result = subprocess.run(["git", *args], capture_output=True, text=True)
    if result.returncode != 0:
        return ""
    return result.stdout


def _git_completion_candidates(comp_type: CompletionType) -> list[str]:
    """Fetch git completion candidates for a given completion type."""
    if comp_type == CompletionType.BRANCH:
        stdout = _git_run_text(["branch", "-a"])
        lines = [
            ln.strip().lstrip("* ").replace("remotes/", "")
            for ln in stdout.splitlines()
            if ln.strip()
        ]
        return sorted(set(lines))

    if comp_type == CompletionType.FILE:
        stdout1 = _git_run_text(["status", "--porcelain"])
        stdout2 = _git_run_text(["ls-files", "--others", "--exclude-standard"])
        lines = []
        for ln in stdout1.splitlines():
            if len(ln) > 3:
                lines.append(ln[3:].strip())
        lines.extend(ln.strip() for ln in stdout2.splitlines() if ln.strip())
        return sorted(set(lines))

    if comp_type == CompletionType.COMMIT:
        stdout = _git_run_text(["log", "--oneline", "--max-count=1000"])
        return [
            ln.split(None, 1)[0]
            for ln in stdout.splitlines()
            if ln.strip()
        ]

    if comp_type == CompletionType.REMOTE:
        stdout = _git_run_text(["remote"])
        return sorted(set(ln.strip() for ln in stdout.splitlines() if ln.strip()))

    if comp_type == CompletionType.TAG:
        stdout = _git_run_text(["tag"])
        return sorted(set(ln.strip() for ln in stdout.splitlines() if ln.strip()))

    if comp_type == CompletionType.STASH:
        stdout = _git_run_text(["stash", "list"])
        return [ln.split(":", 1)[0] for ln in stdout.splitlines() if ln.strip()]

    if comp_type == CompletionType.REF:
        stdout = _git_run_text(["for-each-ref", "--format=%(refname:short)"])
        return sorted(set(ln.strip() for ln in stdout.splitlines() if ln.strip()))

    return []


def make_candidate_provider(
    comp: Optional[CompletionType],
) -> Optional[callable]:
    """Build a candidate provider callback for read_line_with_completion.

    Args:
        comp: Completion type for the argument.

    Returns:
        A callable that takes a prefix string and returns matching candidates,
        or None if no completion is configured.
    """
    if comp is None:
        return None

    candidates = _git_completion_candidates(comp)

    def provider(prefix: str) -> list[str]:
        return [can for can in candidates if can.startswith(prefix)]

    return provider
