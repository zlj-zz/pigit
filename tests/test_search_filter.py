# -*- coding: utf-8 -*-
"""
Module: tests/test_search_filter.py
Description: Tests for SearchFilter and panel search help bindings.
Author: Zev
Date: 2026-08-17
"""

from __future__ import annotations

from unittest.mock import Mock

from pigit.app_search_filter import SearchFilter
from pigit.termui import keys


def test_inactive_slash_not_captured():
    """``/`` is a panel bind_action; SearchFilter must not swallow it when idle."""
    applied = []
    filt = SearchFilter(lambda: applied.append(True))
    assert filt.handle_key("/") is False
    assert filt.active is False
    assert applied == []


def test_enter_activates_search():
    applied = []
    filt = SearchFilter(lambda: applied.append(True))
    filt.enter()
    assert filt.active is True
    assert filt.query == ""
    assert applied == [True]


def test_active_typing_updates_query():
    filt = SearchFilter(lambda: None)
    filt.enter()
    assert filt.handle_key("a") is True
    assert filt.handle_key("b") is True
    assert filt.query == "ab"
    assert filt.handle_key(keys.KEY_BACKSPACE) is True
    assert filt.query == "a"
    assert filt.handle_key(keys.KEY_ESC) is True
    assert filt.active is False


def test_status_help_includes_search():
    from pigit.app_status import StatusPanel
    from pigit.viewmodels.status import IStatusViewModel
    from pigit.termui.reactive import Signal

    vm = Mock(spec=IStatusViewModel)
    vm.items = Signal([])
    panel = StatusPanel(vm=vm)
    entries = panel.get_help_entries()
    assert ("/", "Filter file list by name") in entries


def test_commit_help_includes_search():
    from pigit.app_commit import CommitPanel
    from pigit.viewmodels.commit import ICommitViewModel
    from pigit.termui.reactive import Signal

    vm = Mock(spec=ICommitViewModel)
    vm.items = Signal([])
    panel = CommitPanel(vm=vm)
    entries = panel.get_help_entries()
    assert ("/", "Filter commit list by message or SHA") in entries
