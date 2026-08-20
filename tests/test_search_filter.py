# -*- coding: utf-8 -*-
"""
Module: tests/test_search_filter.py
Description: Tests for ItemList search mode and panel search help bindings.
Author: Zev
Date: 2026-08-17
"""

from __future__ import annotations

from unittest.mock import Mock

from pigit.termui import keys
from pigit.termui.widgets import ItemList


def test_inactive_slash_not_captured():
    """``/`` is a panel bind_action; search_handle_key must not swallow it when idle."""
    applied = []
    sel = ItemList(content=["a"], on_search_changed=lambda: applied.append(True))
    assert sel.search_handle_key("/") is False
    assert sel.search_active is False
    assert applied == []


def test_enter_activates_search():
    applied = []
    sel = ItemList(content=["a"], on_search_changed=lambda: applied.append(True))
    sel.enter_search()
    assert sel.search_active is True
    assert sel.search_query == ""
    assert applied == [True]


def test_active_typing_updates_query():
    sel = ItemList(content=["a"])
    sel.enter_search()
    assert sel.search_handle_key("a") is True
    assert sel.search_handle_key("b") is True
    assert sel.search_query == "ab"
    assert sel.search_handle_key(keys.KEY_BACKSPACE) is True
    assert sel.search_query == "a"
    assert sel.search_handle_key(keys.KEY_ESC) is True
    assert sel.search_active is False


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
