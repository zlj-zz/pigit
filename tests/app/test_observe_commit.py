# -*- coding: utf-8 -*-
"""
Module: tests/app/test_observe_commit.py
Description: An external commit (HEAD/refs change) must reload the Commit panel.
Author: Zev
Date: 2026-09-25
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from pigit.app import PigitApplication
from pigit.app_commit import CommitPanel
from pigit.app_observe import ObserveDeps, ObserveHost
from pigit.app_stash import StashPanel
from pigit.app_status import StatusPanel
from pigit.config_data import AppConfig
from pigit.observe.types import ChangeBatch, ChangeKind, ObserveContext
from pigit.viewmodels.status import IStatusViewModel


@pytest.fixture
def app():
    application = PigitApplication(config=AppConfig(repo_observe=False))
    application.build_root()
    yield application


def _make_host(app, *, visible, refresh=None) -> ObserveHost:
    status_vm = Mock(spec=IStatusViewModel)
    status_vm.items.value = []
    stash_vm = Mock(spec=IStatusViewModel)
    stash_vm.load_stashes.return_value = []
    deps = ObserveDeps(
        get_git=lambda: Mock(),
        get_repo_path=lambda: "/repo",
        get_config=lambda: AppConfig(observe_worktree=True),
        get_status_vm=lambda: status_vm,
        get_tab_view=lambda: SimpleNamespace(visible=visible),
        get_status_panel=lambda: StatusPanel(vm=status_vm, nerd_icons=False),
        get_stash_panel=lambda: StashPanel(vm=stash_vm),
        get_preview_panel=lambda: None,
        get_log_graph_preview=lambda: None,
        get_diff_preview_wanted=lambda: False,
        get_log_graph_wanted=lambda: False,
        get_is_large_screen=lambda: False,
        get_root=lambda: None,
        get_loop=lambda: None,
        schedule_reload_header=Mock(),
        refresh_header_dirty=Mock(),
        refresh_list_panel=refresh or app._refresh_list_panel,
    )
    host = ObserveHost(deps)
    host._observe_ctx = ObserveContext(
        repo_root="/repo", git_dir="/repo/.git", common_dir="/repo/.git"
    )
    return host


def _batch(*kinds: ChangeKind) -> ChangeBatch:
    return ChangeBatch(kinds=frozenset(kinds), paths=frozenset())


def test_commit_focused_head_batch_reloads_commit_panel(app):
    """`git commit` elsewhere moves HEAD/refs: the Commit list must reload."""
    commit = CommitPanel(vm=Mock())
    refresh = Mock()
    host = _make_host(app, visible=commit, refresh=refresh)

    host.on_batch(_batch(ChangeKind.HEAD, ChangeKind.REFS))

    refresh.assert_called_once_with(commit)


def test_commit_focused_refs_batch_reloads_commit_panel(app):
    """A commit that only writes the branch ref still counts as a change."""
    commit = CommitPanel(vm=Mock())
    refresh = Mock()
    host = _make_host(app, visible=commit, refresh=refresh)

    host.on_batch(_batch(ChangeKind.REFS))

    refresh.assert_called_once_with(commit)
