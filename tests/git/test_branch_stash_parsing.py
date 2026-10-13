# -*- coding: utf-8 -*-
"""
Module: tests/git/test_branch_stash_parsing.py
Description: Branch and stash field parsing, including names containing "|".
Author: Zev
Date: 2026-10-05
"""

from __future__ import annotations

from pathlib import Path

from pigit.ext.executor_factory import MockExecutor
from pigit.git import GitApi

# The loaders ask git for NUL-separated fields. Written as %00 in the format
# string because `git branch --format` is the for-each-ref engine, which only
# expands bare hex — the %x00 spelling belongs to `git log`.
NUL = "\x00"


def _branch_line(head: str, name: str, ref: str, upstream: str, track: str, ts: str):
    return NUL.join([head, name, ref, upstream, track, ts])


def _git(output: str) -> GitApi:
    """A GitApi whose every command returns *output*."""
    return GitApi(executor=MockExecutor(default=(0, "", output)), path="/repo")


def test_a_branch_name_may_contain_a_pipe():
    """`|` was the old separator, so such a name shifted every field after it:
    the name, the upstream and the ahead/behind counts all came out wrong."""
    out = _branch_line(
        " ", "feature/a|b", "refs/heads/feature/a|b", "", "", "1791206613"
    )

    branches = _git(out).load_branches()

    assert [b.name for b in branches] == ["feature/a|b"]


def test_a_non_head_line_still_parses():
    """The HEAD field is a space for every branch that is not HEAD, and
    ``resp.strip()`` eats leading whitespace — including the separator
    itself if that separator is whitespace. NUL is not, so the empty first
    field survives."""
    out = _branch_line(" ", "main", "refs/heads/main", "", "", "1791206613")

    branches = _git(out).load_branches()

    assert len(branches) == 1
    assert branches[0].name == "main"
    assert branches[0].is_head is False


def test_the_head_field_marks_the_current_branch():
    out = (
        _branch_line(" ", "main", "refs/heads/main", "", "", "100")
        + "\n"
        + _branch_line("*", "dev", "refs/heads/dev", "", "", "200")
    )

    branches = _git(out).load_branches()

    assert [(b.name, b.is_head) for b in branches] == [("main", False), ("dev", True)]


def test_the_tip_date_is_parsed():
    out = _branch_line("*", "dev", "refs/heads/dev", "", "", "1791206613")

    assert _git(out).load_branches()[0].committed_at == 1791206613


def test_an_unparseable_date_becomes_zero_rather_than_raising():
    """The field is read by index; a non-numeric one must degrade to "no
    date", not take the whole branch list down with it."""
    out = _branch_line("*", "dev", "refs/heads/dev", "", "", "weird")

    assert _git(out).load_branches()[0].committed_at == 0


def test_a_stash_subject_may_contain_a_pipe():
    """The subject is last and read as the whole remainder, so a "|" inside
    it cannot truncate the message."""
    out = "stash@{0}|9551b7e4|1791206613|On main: fix a|b pipe\n"

    stashes = _git(out).load_stashes()

    assert [s.msg for s in stashes] == ["On main: fix a|b pipe"]


def test_the_stash_date_is_parsed():
    out = "stash@{0}|9551b7e4|1791206613|WIP on main\n"

    assert _git(out).load_stashes()[0].when == 1791206613


def test_an_unparseable_stash_date_becomes_zero():
    out = "stash@{0}|9551b7e4|nope|WIP on main\n"

    assert _git(out).load_stashes()[0].when == 0


# ── The command itself, not just the parsing of its output ──
#
# Everything above feeds canned NUL-separated output straight to the parser,
# so it exercises the split and nothing else. The trap this batch had to fix
# lives in the *format string*: `%00` expands, `%x00` and `%x1f` do not —
# `git branch --format` is the for-each-ref engine and only takes bare hex.
# Without the assertions below, changing it back keeps every test green while
# the real panel fails to load at all.


def _executor(output: str = "") -> MockExecutor:
    return MockExecutor(default=(0, "", output))


def test_load_branches_asks_git_for_bare_hex_fields():
    ex = _executor()
    GitApi(executor=ex, path="/repo").load_branches()

    (cmd, _flags, _kw), *_ = ex.exec_calls
    assert "%00" in cmd, f"for-each-ref needs bare hex, got: {cmd}"
    assert "%x00" not in cmd and "%x1f" not in cmd, f"pretty-engine spelling: {cmd}"
    assert "committerdate" in cmd, "the date field is what the row renders"


def test_load_stashes_asks_git_for_a_trailing_subject():
    ex = _executor()
    GitApi(executor=ex, path="/repo").load_stashes()

    (cmd, _flags, _kw), *_ = ex.exec_calls
    # The subject must stay last, or a "|" inside it truncates the message.
    assert cmd.index("%s") > cmd.index("%at")
