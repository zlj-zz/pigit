# -*- coding: utf-8 -*-
"""
Module: tests/app/test_observe_stash.py
Description: ObserveHost treats the Status tab (Status + Stash siblings) as
one observation unit — stash changes refresh the Stash list even while Status
holds focus, and worktree roots mount on either sibling.
Author: Zev
Date: 2026-08-30
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from pigit.app import PigitApplication
from pigit.app_branch import BranchPanel
from pigit.app_commit import CommitPanel
from pigit.app_observe import ObserveDeps, ObserveHost
from pigit.app_stash import StashPanel
from pigit.app_status import StatusPanel
from pigit.config_data import AppConfig
from pigit.observe.types import ChangeBatch, ChangeKind, ObserveContext
from pigit.viewmodels.status import IStatusViewModel


@pytest.fixture
def app():
    """Mounted app whose real _refresh_list_panel drives the panels."""
    application = PigitApplication(config=AppConfig(repo_observe=False))
    application.build_root()
    yield application


def _make_host(
    app,
    *,
    visible,
    status_vm: Mock | None = None,
    stash_vm: Mock | None = None,
    config: AppConfig | None = None,
    refresh=None,
) -> tuple[ObserveHost, StatusPanel, StashPanel]:
    """ObserveHost over the app's real refresh path, with Mock VMs.

    ``visible`` is the presentation leaf (real panel instance); Status/Stash
    siblings are constructed fresh with the given Mock VMs so the refresh
    path never touches git.
    """
    status_vm = status_vm or Mock(spec=IStatusViewModel)
    status_vm.items.value = []  # no status files → no per-file WatchRoots
    stash_vm = stash_vm or Mock(spec=IStatusViewModel)
    stash_vm.load_stashes.return_value = []
    status_panel = StatusPanel(vm=status_vm, nerd_icons=False)
    stash_panel = StashPanel(vm=stash_vm)
    deps = ObserveDeps(
        get_git=lambda: Mock(),
        get_repo_path=lambda: "/repo",
        get_config=lambda: config or AppConfig(observe_worktree=True),
        get_status_vm=lambda: status_vm,
        get_tab_view=lambda: SimpleNamespace(visible=visible),
        get_status_panel=lambda: status_panel,
        get_stash_panel=lambda: stash_panel,
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
    return host, status_panel, stash_panel


def _batch(*kinds: ChangeKind) -> ChangeBatch:
    return ChangeBatch(kinds=frozenset(kinds), paths=frozenset())


# ── app wiring ──


def test_app_wires_status_and_stash_panels_into_deps(app):
    deps = app._observe_host._deps
    assert deps.get_status_panel() is app._status_panel
    assert deps.get_stash_panel() is app._stash_panel


# ── on_batch: Status tab is the observation unit ──


def test_status_focused_stash_batch_refreshes_stash_panel(app):
    """Stash change while Status holds focus must reload the Stash list."""
    stash_vm = Mock(spec=IStatusViewModel)
    status_vm = Mock(spec=IStatusViewModel)
    status = StatusPanel(vm=status_vm, nerd_icons=False)
    host, _status_panel, _stash_panel = _make_host(
        app, visible=status, status_vm=status_vm, stash_vm=stash_vm
    )
    host.on_batch(_batch(ChangeKind.STASH))
    stash_vm.load_stashes.assert_called_once()


def test_status_focused_refs_batch_refreshes_stash_panel(app):
    """O3: REFS (first stash's refs/stash dir signal) also reloads Stash."""
    stash_vm = Mock(spec=IStatusViewModel)
    status_vm = Mock(spec=IStatusViewModel)
    status = StatusPanel(vm=status_vm, nerd_icons=False)
    host, _status_panel, _stash_panel = _make_host(
        app, visible=status, status_vm=status_vm, stash_vm=stash_vm
    )
    host.on_batch(_batch(ChangeKind.REFS))
    stash_vm.load_stashes.assert_called_once()


def test_stash_focused_worktree_meta_refreshes_status_panel(app):
    """Worktree changes while Stash holds focus must refresh Status."""
    status_vm = Mock(spec=IStatusViewModel)
    stash_vm = Mock(spec=IStatusViewModel)
    stash = StashPanel(vm=stash_vm)
    host, _status_panel, _stash_panel = _make_host(
        app, visible=stash, status_vm=status_vm, stash_vm=stash_vm
    )
    host.on_batch(_batch(ChangeKind.WORKTREE_META))
    status_vm.refresh.assert_called_once()


def test_stash_focused_index_batch_refreshes_status_panel(app):
    status_vm = Mock(spec=IStatusViewModel)
    stash_vm = Mock(spec=IStatusViewModel)
    stash = StashPanel(vm=stash_vm)
    host, _status_panel, _stash_panel = _make_host(
        app, visible=stash, status_vm=status_vm, stash_vm=stash_vm
    )
    host.on_batch(_batch(ChangeKind.INDEX))
    status_vm.refresh.assert_called_once()


# ── build_roots: Status tab mounts the worktree root ──


def test_build_roots_stash_leaf_attaches_worktree(app):
    host, _status_panel, _stash_panel = _make_host(
        app, visible=StashPanel(vm=Mock(spec=IStatusViewModel))
    )
    roots = host.build_roots()
    assert any(r.kind == "worktree" for r in roots)
    assert host._worktree_watched is True


def test_build_roots_status_leaf_attaches_worktree(app):
    status = StatusPanel(vm=Mock(spec=IStatusViewModel), nerd_icons=False)
    host, _status_panel, _stash_panel = _make_host(app, visible=status)
    roots = host.build_roots()
    assert any(r.kind == "worktree" for r in roots)
    assert host._worktree_watched is True


def test_build_roots_branch_leaf_skips_worktree(app):
    branch = BranchPanel(vm=Mock(), get_git=lambda: Mock())
    host, _status_panel, _stash_panel = _make_host(app, visible=branch)
    roots = host.build_roots()
    assert all(r.kind != "worktree" for r in roots)
    assert host.worktree_dirty is None


def test_build_roots_commit_leaf_skips_worktree(app):
    commit = CommitPanel(vm=Mock())
    host, _status_panel, _stash_panel = _make_host(app, visible=commit)
    roots = host.build_roots()
    assert all(r.kind != "worktree" for r in roots)
    assert host.worktree_dirty is None


# ── regression: non-Status-tab panels keep their own refresh scope ──


def test_branch_focused_refs_refreshes_branch_only(app):
    branch = BranchPanel(vm=Mock(), get_git=lambda: Mock())
    refresh = Mock()
    host, _status_panel, stash_panel = _make_host(app, visible=branch, refresh=refresh)
    host.on_batch(_batch(ChangeKind.REFS))
    refresh.assert_called_once_with(branch)
    # Stash panel must not be touched while Branch is the active tab.
    stash_panel._vm.load_stashes.assert_not_called()
