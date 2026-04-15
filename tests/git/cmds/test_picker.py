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
from pigit.git.cmds._picker import (
    _build_context_signals,
    _context_score,
    _sort_picker_entries,
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
        signals = _build_context_signals()
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

        signals = _build_context_signals()
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
        signals = _build_context_signals()
        assert signals["has_unstaged"] is False
        assert signals["has_staged"] is False
        assert signals["has_conflict"] is False


class TestContextScore:
    def test_index_boosted_when_unstaged(self):
        entry = CmdNewEntry(name="i.a", help_text="add all", category="index", is_dangerous=False, has_args=False)
        signals = {"has_unstaged": True, "has_staged": False, "has_conflict": False}
        assert _context_score(entry, signals) == 100

    def test_commit_boosted_when_staged(self):
        entry = CmdNewEntry(name="c", help_text="commit", category="commit", is_dangerous=False, has_args=False)
        signals = {"has_unstaged": False, "has_staged": True, "has_conflict": False}
        assert _context_score(entry, signals) == 100

    def test_conflict_boosted_when_conflict(self):
        entry = CmdNewEntry(name="C.r", help_text="resolve", category="conflict", is_dangerous=False, has_args=False)
        signals = {"has_unstaged": False, "has_staged": False, "has_conflict": True}
        assert _context_score(entry, signals) == 100

    def test_merge_boosted_when_conflict(self):
        entry = CmdNewEntry(name="m.a", help_text="abort", category="merge", is_dangerous=False, has_args=False)
        signals = {"has_unstaged": False, "has_staged": False, "has_conflict": True}
        assert _context_score(entry, signals) == 100

    def test_no_boost_when_no_signal(self):
        entry = CmdNewEntry(name="b", help_text="branch", category="branch", is_dangerous=False, has_args=False)
        signals = {"has_unstaged": True, "has_staged": False, "has_conflict": False}
        assert _context_score(entry, signals) == 0


class TestSortPickerEntries:
    def test_mru_comes_first(self):
        entries = [
            CmdNewEntry(name="a", help_text="", category="branch", is_dangerous=False, has_args=False),
            CmdNewEntry(name="b", help_text="", category="branch", is_dangerous=False, has_args=False),
            CmdNewEntry(name="c", help_text="", category="branch", is_dangerous=False, has_args=False),
        ]
        mru = ["c", "a"]
        signals = {"has_unstaged": False, "has_staged": False, "has_conflict": False}
        sorted_entries = _sort_picker_entries(entries, mru, signals)
        assert [e.name for e in sorted_entries] == ["c", "a", "b"]

    def test_context_score_breaks_tie(self):
        entries = [
            CmdNewEntry(name="b", help_text="", category="branch", is_dangerous=False, has_args=False),
            CmdNewEntry(name="i", help_text="", category="index", is_dangerous=False, has_args=False),
        ]
        mru = []
        signals = {"has_unstaged": True, "has_staged": False, "has_conflict": False}
        sorted_entries = _sort_picker_entries(entries, mru, signals)
        assert [e.name for e in sorted_entries] == ["i", "b"]

    def test_mru_overrides_context_score(self):
        entries = [
            CmdNewEntry(name="b", help_text="", category="branch", is_dangerous=False, has_args=False),
            CmdNewEntry(name="i", help_text="", category="index", is_dangerous=False, has_args=False),
        ]
        mru = ["b"]
        signals = {"has_unstaged": True, "has_staged": False, "has_conflict": False}
        sorted_entries = _sort_picker_entries(entries, mru, signals)
        # b is in MRU, so it comes before i even though i has context boost
        assert [e.name for e in sorted_entries] == ["b", "i"]

    def test_alphabetical_fallback(self):
        entries = [
            CmdNewEntry(name="z", help_text="", category="branch", is_dangerous=False, has_args=False),
            CmdNewEntry(name="a", help_text="", category="branch", is_dangerous=False, has_args=False),
        ]
        mru = []
        signals = {"has_unstaged": False, "has_staged": False, "has_conflict": False}
        sorted_entries = _sort_picker_entries(entries, mru, signals)
        assert [e.name for e in sorted_entries] == ["a", "z"]


class TestPickerCompletionDelegation:
    def test_execute_uses_completion_when_arg_completion_present(self, monkeypatch):
        """_execute_command delegates to read_line_with_completion when arg_completion is set."""
        from pigit.cmdparse.completion.base import CompletionType
        from pigit.git.cmds import GitCommandNew
        from pigit.git.cmds._picker import CmdNewPickerLoop

        entry = CmdNewEntry(
            name="b.d",
            help_text="delete",
            category="branch",
            is_dangerous=False,
            has_args=True,
            arg_completion=CompletionType.BRANCH,
        )
        processor = GitCommandNew()
        loop = CmdNewPickerLoop.__new__(CmdNewPickerLoop)
        loop._print_only = False
        loop._alt = False
        loop._renderer = mock.Mock()

        captured = {}
        monkeypatch.setattr(
            "pigit.git.cmds._picker.read_line_with_completion",
            lambda *, write, flush, prompt, completion_type, hint_styler=None: (
                captured.update({"type": completion_type}) or "main"
            ),
        )

        def fake_execute(name, args):
            captured["name"] = name
            captured["args"] = args
            return 0, "ok"

        monkeypatch.setattr(processor, "execute", fake_execute)
        result = loop._execute_command(entry, processor)
        assert result == (0, "ok")
        assert captured["name"] == "b.d"
        assert captured["args"] == ["main"]
        assert captured["type"] == CompletionType.BRANCH

    def test_execute_falls_back_to_cancellable_when_no_arg_completion(self, monkeypatch):
        """_execute_command uses read_line_cancellable when arg_completion is absent."""
        from pigit.git.cmds import GitCommandNew
        from pigit.git.cmds._picker import CmdNewPickerLoop

        entry = CmdNewEntry(
            name="custom",
            help_text="custom",
            category="script",
            is_dangerous=False,
            has_args=True,
            arg_completion=None,
        )
        processor = GitCommandNew()
        loop = CmdNewPickerLoop.__new__(CmdNewPickerLoop)
        loop._print_only = False
        loop._alt = False
        loop._renderer = mock.Mock()

        captured = {}
        monkeypatch.setattr(
            "pigit.git.cmds._picker.read_line_cancellable",
            lambda *, write, flush, prompt: (
                captured.update({"used": True}) or "value"
            ),
        )

        def fake_execute(name, args):
            captured["name"] = name
            captured["args"] = args
            return 0, "ok"

        monkeypatch.setattr(processor, "execute", fake_execute)
        result = loop._execute_command(entry, processor)
        assert result == (0, "ok")
        assert captured.get("used") is True
        assert captured["args"] == ["value"]
