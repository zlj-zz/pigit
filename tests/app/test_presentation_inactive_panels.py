"""
Module: tests/app/test_presentation_inactive_panels.py
Description: Body panels dim via presentation_fg when MODAL/SHEET steals presentation.
Author: Zev
Date: 2026-08-24
"""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from pigit.app_branch import BranchPanel
from pigit.app_commit import CommitPanel
from pigit.app_status import StatusPanel
from pigit.app_stash import StashPanel
from pigit.app_theme import THEME
from pigit.git.model import Branch, Commit, File, Stash
from pigit.termui import Component, ComponentRoot
from pigit.termui._runtime_context import (
    RuntimeContext,
    _runtime_ctx,
    reset_focus_manager,
    reset_overlay_host,
    set_focus_manager,
    set_overlay_host,
)
from pigit.termui.reactive import Signal
from pigit.termui.theme import get_theme, set_theme
from pigit.viewmodels.branch import IBranchViewModel
from pigit.viewmodels.commit import ICommitViewModel
from pigit.viewmodels.status import IStatusViewModel


@pytest.fixture(autouse=True)
def _runtime_and_theme():
    """Pigit theme + fresh runtime; clear overlay / focus after each test."""
    prev = get_theme()
    set_theme(THEME)
    runtime = RuntimeContext()
    token = _runtime_ctx.set(runtime)
    yield
    reset_overlay_host()
    reset_focus_manager()
    _runtime_ctx.reset(token)
    set_theme(prev)


class _SheetChild(Component):
    def paint(self, surface) -> None:
        pass


def _steal_presentation() -> ComponentRoot:
    """Open a sheet so ``get_overlay_host().is_presentation_stolen()`` is True."""
    body = _SheetChild()
    root = ComponentRoot(body)
    root.resize((80, 24))
    set_overlay_host(root)
    root.show_sheet(_SheetChild(), height=4)
    return root


def _status_file(name: str = "a.py", short_status: str = "M ") -> File:
    return File(
        name=name,
        display_str=name,
        short_status=short_status,
        has_staged_change=True,
        has_unstaged_change=False,
        tracked=True,
        deleted=False,
        added=False,
        has_merged_conflicts=False,
        has_inline_merged_conflicts=False,
    )


def test_status_filename_inactive_under_steal_xy_semantic_kept() -> None:
    vm = Mock(spec=IStatusViewModel)
    vm.items = Signal([])
    vm.repo_path = "/tmp/repo"
    panel = StatusPanel(vm=vm, default_view="flat")
    panel.files = [_status_file()]
    panel.content = [panel.files[0].display_str]

    left, main, right = panel.describe_row(0, is_cursor=False)
    assert main[0].fg == THEME.fg_primary
    assert left[1].fg == THEME.fg_success  # staged M

    _steal_presentation()
    left, main, right = panel.describe_row(0, is_cursor=False)
    assert main[0].fg == THEME.fg_inactive
    assert left[1].fg == THEME.fg_success
    assert right[0].fg == THEME.fg_success  # Staged label


def test_status_multiselect_keeps_renamed_color_under_steal() -> None:
    vm = Mock(spec=IStatusViewModel)
    vm.items = Signal([])
    vm.repo_path = "/tmp/repo"
    panel = StatusPanel(vm=vm, default_view="flat")
    panel.files = [_status_file()]
    panel.content = [panel.files[0].display_str]
    panel._selected = {0}

    _steal_presentation()
    _left, main, _right = panel.describe_row(0, is_cursor=False)
    assert main[0].fg == THEME.fg_staged_renamed


def test_commit_message_inactive_refs_keep_color() -> None:
    vm = Mock(spec=ICommitViewModel)
    vm.items = Signal([])
    vm.graph_rows = []
    vm.remotes = ()
    panel = CommitPanel(vm=vm)
    commit = Commit(
        "abc1234ffff",
        "fix bug",
        "Zev",
        0,
        "pushed",
        " (HEAD -> main)",
        [],
    )
    panel.commits = [commit]
    panel.content = [commit.msg]
    panel._build_row_cache()

    _left, main, right = panel.describe_row(0, is_cursor=False)
    msg = [s for s in main if s.text == "fix bug"][0]
    assert msg.fg == THEME.fg_primary
    ref_fgs = {s.fg for s in main if s.text in ("HEAD", "main", " -> ")}
    assert THEME.fg_info in ref_fgs
    assert THEME.fg_local_branch in ref_fgs

    _steal_presentation()
    left, main, right = panel.describe_row(0, is_cursor=False)
    msg = [s for s in main if s.text == "fix bug"][0]
    assert msg.fg == THEME.fg_inactive
    sha = [s for s in left if s.text == "abc1234"][0]
    assert sha.fg == THEME.fg_inactive
    assert right[0].fg == THEME.fg_inactive
    ref_fgs = {s.fg for s in main if s.text in ("HEAD", "main")}
    assert THEME.fg_info in ref_fgs
    assert THEME.fg_local_branch in ref_fgs


def test_unpushed_commit_glyph_stays_semantic_under_steal() -> None:
    from pigit.app_types import GraphRow

    vm = Mock(spec=ICommitViewModel)
    vm.items = Signal([])
    vm.remotes = ()
    commit = Commit("deadbeefaaaa", "wip", "Zev", 0, "unpushed", "", [])
    vm.graph_rows = [
        GraphRow(
            lanes_before=[],
            commit_lane=0,
            closed_lanes=[],
            opened_lanes=[],
            lanes_after=["deadbeefaaaa"],
        )
    ]
    panel = CommitPanel(vm=vm)
    panel.commits = [commit]
    panel.content = [commit.msg]
    panel._build_row_cache()

    _steal_presentation()
    left, _main, _right = panel.describe_row(0, is_cursor=False)
    glyph = [s for s in left if s.text.startswith(panel.GRAPH_COMMIT)][0]
    assert glyph.fg == THEME.fg_unpushed_commit


def test_status_dir_summary_stays_fg_dim() -> None:
    vm = Mock(spec=IStatusViewModel)
    vm.items = Signal([])
    vm.repo_path = "/tmp/repo"
    panel = StatusPanel(vm=vm, default_view="tree")
    panel._all_files = [
        _status_file("src/a.py"),
        _status_file("src/b.py"),
    ]
    panel._apply_filter()
    assert panel._row(0) is not None and panel._row(0).kind == "dir"
    _left, _main, right = panel.describe_row(0, is_cursor=False)
    assert right
    assert right[0].fg == THEME.fg_dim


def test_branch_head_remote_keep_local_inactive_under_steal() -> None:
    vm = Mock(spec=IBranchViewModel)
    vm.items = Signal([])
    panel = BranchPanel(vm=vm)
    panel.branches = [
        Branch("main", "0", "0", True),
        Branch("feature", "0", "0", False),
        Branch("origin/main", "?", "?", False, is_remote=True),
    ]
    panel.content = [b.name for b in panel.branches]

    _steal_presentation()
    head_left, _, _ = panel.describe_row(0, is_cursor=False)
    local_left, _, _ = panel.describe_row(1, is_cursor=False)
    remote_left, _, _ = panel.describe_row(2, is_cursor=False)
    assert head_left[0].fg == THEME.fg_local_branch
    assert local_left[0].fg == THEME.fg_inactive
    assert remote_left[0].fg == THEME.fg_remote_branch


def test_stash_message_and_ref_inactive_under_steal() -> None:
    vm = Mock(spec=IStatusViewModel)
    vm.items = Signal([])
    vm.load_stashes.return_value = [
        Stash(ref="stash@{0}", sha="abc0", msg="WIP on main")
    ]
    panel = StashPanel(vm=vm)
    panel.mount()
    panel.on_focus()

    _left, main, right = panel.describe_row(0, is_cursor=False)
    assert main[0].fg == THEME.fg_primary
    assert right[0].fg == THEME.fg_muted

    _steal_presentation()
    _left, main, right = panel.describe_row(0, is_cursor=False)
    assert main[0].fg == THEME.fg_inactive
    assert right[0].fg == THEME.fg_inactive


def test_status_stash_focus_switch_softens_non_leaf() -> None:
    """Status↔Stash co-visible: non-leaf softens; semantic XY stays."""
    status_vm = Mock(spec=IStatusViewModel)
    status_vm.items = Signal([])
    status_vm.repo_path = "/tmp/repo"
    status = StatusPanel(vm=status_vm, default_view="flat")
    status.files = [_status_file()]
    status.content = [status.files[0].display_str]

    stash_vm = Mock(spec=IStatusViewModel)
    stash_vm.items = Signal([])
    stash_vm.load_stashes.return_value = [
        Stash(ref="stash@{0}", sha="abc0", msg="WIP on main")
    ]
    stash = StashPanel(vm=stash_vm)
    stash.mount()
    stash.on_focus()

    root = ComponentRoot(status)
    root.resize((80, 24))
    set_overlay_host(root)
    set_focus_manager(root._focus_manager)

    root._focus_manager.set_focus_chain(status)
    assert status.is_presentation_active() is True
    assert stash.is_presentation_active() is False
    _l, status_main, status_right = status.describe_row(0, is_cursor=False)
    _l, stash_main, stash_right = stash.describe_row(0, is_cursor=False)
    assert status_main[0].fg == THEME.fg_primary
    assert status_right[0].fg == THEME.fg_success
    assert stash_main[0].fg == THEME.fg_muted
    assert stash_right[0].fg == THEME.fg_dim

    root._focus_manager.set_focus_chain(stash)
    assert stash.is_presentation_active() is True
    assert status.is_presentation_active() is False
    _l, status_main, status_right = status.describe_row(0, is_cursor=False)
    _l, stash_main, stash_right = stash.describe_row(0, is_cursor=False)
    assert status_main[0].fg == THEME.fg_muted
    assert status_right[0].fg == THEME.fg_success
    assert stash_main[0].fg == THEME.fg_primary
    assert stash_right[0].fg == THEME.fg_muted
