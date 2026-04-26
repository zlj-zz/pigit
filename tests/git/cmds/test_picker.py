# -*- coding: utf-8 -*-
"""
Module: tests/git/cmds/test_picker.py
Description: Tests for cmd picker sorting and context awareness.
Author: Zev
Date: 2026-04-14
"""

import logging
from unittest import mock

import pytest

from pigit.config import Config
from pigit.context import Context
from pigit.ext.executor_factory import ExecutorFactory, MockExecutor
from pigit.git.cmds._picker_sorter import (
    build_context_signals,
    context_score,
    sort_picker_entries,
)
from pigit.git.cmds._picker_adapter import CmdNewEntry
from pigit.git.model import File
from pigit.git.repo import Repo


@pytest.fixture(autouse=True)
def _isolate_context_and_factory():
    Context.detach()
    ExecutorFactory.reset()
    yield
    Context.detach()
    ExecutorFactory.reset()


class TestBuildContextSignals:
    def test_no_context_returns_all_false(self):
        signals = build_context_signals()
        assert signals == {
            "has_unstaged": False,
            "has_staged": False,
            "has_conflict": False,
        }

    def test_repo_status_detects_signals(self, monkeypatch):
        cfg = Config(path="/nonexistent/pigit-test.conf", version="0", auto_load=False)
        ex = MockExecutor()
        repo = Repo(executor=ex)
        ctx = Context(config=cfg, executor=ex, repo=repo, log=logging.getLogger("test"))
        Context.install(ctx)

        mock_files = [
            File(
                name="a.py",
                display_str="a.py",
                short_status=" M",
                has_staged_change=False,
                has_unstaged_change=True,
                tracked=True,
                deleted=False,
                added=False,
                has_merged_conflicts=False,
                has_inline_merged_conflicts=False,
            ),
            File(
                name="b.py",
                display_str="b.py",
                short_status="M ",
                has_staged_change=True,
                has_unstaged_change=False,
                tracked=True,
                deleted=False,
                added=False,
                has_merged_conflicts=False,
                has_inline_merged_conflicts=False,
            ),
            File(
                name="c.py",
                display_str="c.py",
                short_status="UU",
                has_staged_change=False,
                has_unstaged_change=True,
                tracked=True,
                deleted=False,
                added=False,
                has_merged_conflicts=True,
                has_inline_merged_conflicts=True,
            ),
        ]
        monkeypatch.setattr(repo, "load_status", lambda: mock_files)

        signals = build_context_signals()
        assert signals["has_unstaged"] is True
        assert signals["has_staged"] is True
        assert signals["has_conflict"] is True

    def test_repo_status_exception_falls_back(self):
        cfg = Config(path="/nonexistent/pigit-test.conf", version="0", auto_load=False)
        ex = MockExecutor()
        repo = Repo(executor=ex)
        ctx = Context(config=cfg, executor=ex, repo=repo, log=logging.getLogger("test"))
        Context.install(ctx)

        # repo.load_status may raise without a real git repo
        signals = build_context_signals()
        assert signals["has_unstaged"] is False
        assert signals["has_staged"] is False
        assert signals["has_conflict"] is False


class TestContextScore:
    def test_index_boosted_when_unstaged(self):
        entry = CmdNewEntry(
            name="i.a",
            help_text="add all",
            category="index",
            is_dangerous=False,
            has_args=False,
        )
        signals = {"has_unstaged": True, "has_staged": False, "has_conflict": False}
        assert context_score(entry, signals) == 100

    def test_commit_boosted_when_staged(self):
        entry = CmdNewEntry(
            name="c",
            help_text="commit",
            category="commit",
            is_dangerous=False,
            has_args=False,
        )
        signals = {"has_unstaged": False, "has_staged": True, "has_conflict": False}
        assert context_score(entry, signals) == 100

    def test_conflict_boosted_when_conflict(self):
        entry = CmdNewEntry(
            name="C.r",
            help_text="resolve",
            category="conflict",
            is_dangerous=False,
            has_args=False,
        )
        signals = {"has_unstaged": False, "has_staged": False, "has_conflict": True}
        assert context_score(entry, signals) == 100

    def test_merge_boosted_when_conflict(self):
        entry = CmdNewEntry(
            name="m.a",
            help_text="abort",
            category="merge",
            is_dangerous=False,
            has_args=False,
        )
        signals = {"has_unstaged": False, "has_staged": False, "has_conflict": True}
        assert context_score(entry, signals) == 100

    def test_no_boost_when_no_signal(self):
        entry = CmdNewEntry(
            name="b",
            help_text="branch",
            category="branch",
            is_dangerous=False,
            has_args=False,
        )
        signals = {"has_unstaged": True, "has_staged": False, "has_conflict": False}
        assert context_score(entry, signals) == 0


class TestSortPickerEntries:
    def test_mru_comes_first(self):
        entries = [
            CmdNewEntry(
                name="a",
                help_text="",
                category="branch",
                is_dangerous=False,
                has_args=False,
            ),
            CmdNewEntry(
                name="b",
                help_text="",
                category="branch",
                is_dangerous=False,
                has_args=False,
            ),
            CmdNewEntry(
                name="c",
                help_text="",
                category="branch",
                is_dangerous=False,
                has_args=False,
            ),
        ]
        mru = ["c", "a"]
        signals = {"has_unstaged": False, "has_staged": False, "has_conflict": False}
        sorted_entries = sort_picker_entries(entries, mru, signals)
        assert [e.name for e in sorted_entries] == ["c", "a", "b"]

    def test_context_score_breaks_tie(self):
        entries = [
            CmdNewEntry(
                name="b",
                help_text="",
                category="branch",
                is_dangerous=False,
                has_args=False,
            ),
            CmdNewEntry(
                name="i",
                help_text="",
                category="index",
                is_dangerous=False,
                has_args=False,
            ),
        ]
        mru = []
        signals = {"has_unstaged": True, "has_staged": False, "has_conflict": False}
        sorted_entries = sort_picker_entries(entries, mru, signals)
        assert [e.name for e in sorted_entries] == ["i", "b"]

    def test_mru_overrides_context_score(self):
        entries = [
            CmdNewEntry(
                name="b",
                help_text="",
                category="branch",
                is_dangerous=False,
                has_args=False,
            ),
            CmdNewEntry(
                name="i",
                help_text="",
                category="index",
                is_dangerous=False,
                has_args=False,
            ),
        ]
        mru = ["b"]
        signals = {"has_unstaged": True, "has_staged": False, "has_conflict": False}
        sorted_entries = sort_picker_entries(entries, mru, signals)
        # b is in MRU, so it comes before i even though i has context boost
        assert [e.name for e in sorted_entries] == ["b", "i"]

    def test_alphabetical_fallback(self):
        entries = [
            CmdNewEntry(
                name="z",
                help_text="",
                category="branch",
                is_dangerous=False,
                has_args=False,
            ),
            CmdNewEntry(
                name="a",
                help_text="",
                category="branch",
                is_dangerous=False,
                has_args=False,
            ),
        ]
        mru = []
        signals = {"has_unstaged": False, "has_staged": False, "has_conflict": False}
        sorted_entries = sort_picker_entries(entries, mru, signals)
        assert [e.name for e in sorted_entries] == ["a", "z"]
