# -*- coding: utf-8 -*-
"""
Module: tests/git/test_reflog.py
Description: GitApi.list_reflog parsing (tab fields, tabbed message, empty).
Author: Zev
Date: 2026-08-31
"""

from __future__ import annotations

from pigit.ext.executor_factory import MockExecutor
from pigit.git import GitApi

_FMT = "git reflog -n 50 --format=%H%x09%gD%x09%gs%x09%at"


def test_list_reflog_parses_entries() -> None:
    ex = MockExecutor(
        responses={
            _FMT: (
                0,
                "",
                "abc" + "1" * 37 + "\tHEAD@{0}\tcommit: add feature\t1700000000\n"
                "def" + "2" * 37 + "\tHEAD@{1}\tcommit (initial): init\t1690000000\n",
            )
        }
    )
    entries = GitApi(executor=ex, path="/repo").list_reflog()
    assert len(entries) == 2
    assert entries[0].sha == "abc" + "1" * 37
    assert entries[0].refish == "HEAD@{0}"
    assert entries[0].message == "commit: add feature"
    assert entries[0].when == 1700000000
    assert entries[1].refish == "HEAD@{1}"


def test_list_reflog_message_with_tab_kept_whole() -> None:
    """%gs may contain a tab; the message stays whole and ``when`` stays clean."""
    ex = MockExecutor(
        responses={
            _FMT: (
                0,
                "",
                "abc" + "1" * 37 + "\tHEAD@{0}\tcommit: foo\tbar\t1700000000\n"
                "def" + "2" * 37 + "\tHEAD@{1}\tcommit: plain\t1690000000\n",
            )
        }
    )
    entries = GitApi(executor=ex, path="/repo").list_reflog()
    assert len(entries) == 2
    assert entries[0].message == "commit: foo\tbar"
    assert entries[0].when == 1700000000
    assert entries[1].message == "commit: plain"


def test_list_reflog_empty_output_returns_empty() -> None:
    ex = MockExecutor(responses={_FMT: (0, "", "")})
    assert GitApi(executor=ex, path="/repo").list_reflog() == []


def test_list_reflog_malformed_line_skipped() -> None:
    ex = MockExecutor(
        responses={
            _FMT: (
                0,
                "",
                "abc" + "1" * 37 + "\tHEAD@{0}\tcommit: ok\t1700000000\n"
                "junk-line-without-tabs\n"
                "def" + "2" * 37 + "\tHEAD@{2}\tcommit: bad-when\tnot-a-number\n",
            )
        }
    )
    entries = GitApi(executor=ex, path="/repo").list_reflog()
    assert len(entries) == 1
    assert entries[0].refish == "HEAD@{0}"


def test_list_reflog_failure_returns_empty() -> None:
    """A failed git call must not raise; empty reflog semantics (best-effort)."""
    ex = MockExecutor(responses={_FMT: (128, "fatal: bad", "")})
    assert GitApi(executor=ex, path="/repo").list_reflog() == []
