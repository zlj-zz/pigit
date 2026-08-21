# -*- coding: utf-8 -*-
"""
Module: tests/git/test_file_path.py
Description: File worktree path vs porcelain display_str contract.
Author: Zev
Date: 2026-08-20
"""

from __future__ import annotations

from pigit.git.model import File


def _file(name: str, display_str: str | None = None) -> File:
    shown = display_str if display_str is not None else name
    return File(
        name=name,
        display_str=shown,
        short_status="R ",
        has_staged_change=True,
        has_unstaged_change=False,
        tracked=True,
        deleted=False,
        added=False,
        has_merged_conflicts=False,
        has_inline_merged_conflicts=False,
    )


def test_resolve_status_path_takes_rename_destination():
    assert (
        File.resolve_status_path("src/orig.txt -> src/renamed.txt") == "src/renamed.txt"
    )


def test_resolve_status_path_leaves_plain_path():
    assert File.resolve_status_path("src/a.py") == "src/a.py"


def test_file_name_is_worktree_path_display_keeps_rename_arrow():
    """Status parse must store path in name; porcelain text in display_str."""
    f = _file(
        name="src/renamed.txt",
        display_str="src/orig.txt -> src/renamed.txt",
    )
    assert f.name == "src/renamed.txt"
    assert f.get_file_str() == "src/renamed.txt"
    assert "->" in f.display_str
