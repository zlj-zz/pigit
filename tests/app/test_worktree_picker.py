# -*- coding: utf-8 -*-
"""
Module: tests/app/test_worktree_picker.py
Description: Worktree picker sheet, w-mode toggle, add/remove guards.
Author: Zev
Date: 2026-08-28
"""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

from pigit.app import PigitApplication
from pigit.app_repo_switcher import RepoSwitcherSheet
from pigit.app_worktree_picker import (
    WorktreePickerEntry,
    WorktreePickerSheet,
    build_worktree_picker_entries,
    format_worktree_row,
    parse_add_worktree_input,
)
from pigit.config_data import AppConfig
from pigit.git.api import GitError, WorktreeInfo
from pigit.termui import FeedbackKind
from pigit.termui._runtime_context import RuntimeContext, _runtime_ctx, set_overlay_host
from pigit.termui.root import ComponentRoot


def test_format_worktree_row_marks_current_and_detached():
    info = WorktreeInfo(
        path="/work/a",
        head_sha="abcdef0123456789",
        branch=None,
        is_main=False,
        detached=True,
    )
    text = "".join(s.text for s in format_worktree_row(info, is_current=True))
    assert text.startswith("● ")
    assert "/work/a" in text
    assert "(detached)" in text
    assert "abcdef0" in text


def test_format_worktree_row_branch():
    info = WorktreeInfo(
        path="/work/b",
        head_sha="1234567deadbeef",
        branch="feat/x",
        is_main=False,
        detached=False,
    )
    text = "".join(s.text for s in format_worktree_row(info, is_current=False))
    assert text.startswith("  ")
    assert "feat/x" in text


def test_build_entries_marks_current_by_resolved_path():
    trees = [
        WorktreeInfo("/work/main", "aaa", "main", True, False),
        WorktreeInfo("/work/feat", "bbb", "feat", False, False),
    ]
    entries = build_worktree_picker_entries(trees, current_path="/work/feat")
    assert entries[0].is_current is False
    assert entries[1].is_current is True


def test_parse_add_worktree_input_defaults_branch():
    path, branch = parse_add_worktree_input("/tmp/my-wt")
    assert path == "/tmp/my-wt"
    assert branch == "wt-my-wt"


def test_parse_add_worktree_input_with_branch():
    path, branch = parse_add_worktree_input("/tmp/my-wt feature/x")
    assert path == "/tmp/my-wt"
    assert branch == "feature/x"


def test_worktree_sheet_confirm_calls_switch():
    switched: list[str] = []
    info = WorktreeInfo("/work/feat", "abc", "feat", False, False)
    sheet = WorktreePickerSheet(
        entries=[WorktreePickerEntry(info=info, is_current=False)],
        on_switch=lambda p: switched.append(p),
    )
    sheet.mount()
    with patch("pigit.app_worktree_picker.dismiss_sheet"):
        sheet.confirm()
    assert switched == ["/work/feat"]


def test_worktree_sheet_w_toggles_mode():
    toggled: list[int] = []
    sheet = WorktreePickerSheet(
        entries=[],
        on_switch=lambda _p: None,
        on_toggle_mode=lambda: toggled.append(1),
    )
    sheet.toggle_mode()
    assert toggled == [1]


def test_repo_sheet_w_toggles_mode():
    toggled: list[int] = []
    sheet = RepoSwitcherSheet(
        entries=[],
        on_switch=lambda _p: None,
        on_toggle_mode=lambda: toggled.append(1),
    )
    sheet.toggle_mode()
    assert toggled == [1]


@pytest.fixture
def runtime():
    ctx = RuntimeContext()
    token = _runtime_ctx.set(ctx)
    yield ctx
    _runtime_ctx.reset(token)


def _mount(runtime: RuntimeContext) -> tuple[PigitApplication, ComponentRoot]:
    app = PigitApplication(config=AppConfig(repo_observe=False))
    body = app.build_root()
    root = ComponentRoot(
        body,
        runtime.registry,
        event_bus=app._event_bus,
        key_handlers=app._key_handlers,
    )
    runtime.overlay_host = root
    runtime.focus_manager = root._focus_manager
    set_overlay_host(root)
    root._app_on_event = app.on_event
    app._root = root
    app.setup_root(root)
    root.mount()
    root.resize((100, 30))
    return app, root


def test_open_worktree_picker_lists_and_switch_reuses_switch_repo(runtime):
    app, _root = _mount(runtime)
    trees = [
        WorktreeInfo(app._repo_path, "aaa", "main", True, False),
        WorktreeInfo("/other/wt", "bbb", "feat", False, False),
    ]
    app._git.list_worktrees = Mock(return_value=trees)
    app._switch_repo = Mock()
    with patch("pigit.app.show_sheet") as show:
        app.open_worktree_picker()
        show.assert_called_once()
        panel = show.call_args[0][0]
        assert isinstance(panel, WorktreePickerSheet)
        assert panel._entries[0].is_current is True
    with patch("pigit.app_worktree_picker.dismiss_sheet"):
        panel._activate_index(1)
    app._switch_repo.assert_called_once_with("/other/wt")


def test_remove_current_session_worktree_blocked(runtime):
    app, _root = _mount(runtime)
    info = WorktreeInfo(app._repo_path, "aaa", "main", False, False)
    app._alert_dialog.alert = Mock()
    with patch("pigit.app.show_toast") as toast:
        app._confirm_remove_worktree(info)
        toast.assert_called()
        msg = toast.call_args[0][0]
        assert "先切换" in msg
    app._alert_dialog.alert.assert_not_called()


def test_remove_main_worktree_blocked(runtime):
    app, _root = _mount(runtime)
    info = WorktreeInfo("/elsewhere/main", "aaa", "main", True, False)
    with patch("pigit.app.show_toast") as toast:
        app._confirm_remove_worktree(info)
        assert "主工作树" in toast.call_args[0][0]


def test_add_worktree_failure_toasts(runtime):
    app, _root = _mount(runtime)
    app._git.add_worktree = Mock(side_effect=GitError("path exists"))
    with patch("pigit.app.show_toast") as toast:
        app._on_add_worktree_submit("/tmp/x feature")
        toast.assert_called()
        assert "path exists" in toast.call_args[0][0]
        assert toast.call_args[1].get("kind") == FeedbackKind.ERROR


def test_add_worktree_success_switches(runtime):
    app, _root = _mount(runtime)
    app._git.add_worktree = Mock()
    app._switch_repo = Mock()
    with (
        patch("pigit.app.dismiss_sheet"),
        patch("pigit.app.show_toast"),
    ):
        app._on_add_worktree_submit("/tmp/new-wt mybranch")
    app._git.add_worktree.assert_called_once_with("/tmp/new-wt", "mybranch", new=True)
    app._switch_repo.assert_called_once_with("/tmp/new-wt")


def test_parse_add_worktree_input_quoted_space_path():
    path, branch = parse_add_worktree_input('"/tmp/my wt"')
    assert path == "/tmp/my wt"
    assert branch == "wt-my wt"


def test_parse_add_worktree_input_quoted_path_with_branch():
    path, branch = parse_add_worktree_input('"/tmp/my wt" feature/x')
    assert path == "/tmp/my wt"
    assert branch == "feature/x"


def test_parse_add_worktree_input_extra_token_errors():
    with pytest.raises(ValueError):
        parse_add_worktree_input("/tmp/a b c")


def test_parse_add_worktree_input_empty_errors():
    with pytest.raises(ValueError):
        parse_add_worktree_input("   ")


def test_remove_dirty_worktree_asks_force_then_removes(runtime):
    app, _root = _mount(runtime)
    info = WorktreeInfo("/dirty/wt", "aaa", "feat", False, False)
    app._git.is_worktree_dirty = Mock(return_value=True)
    app._git.remove_worktree = Mock()
    app.open_worktree_picker = Mock()
    callbacks: list[Callable] = []
    app._alert_dialog.alert = Mock(
        side_effect=lambda msg, cb, **kw: callbacks.append(cb)
    )
    with patch("pigit.app.show_toast"):
        app._confirm_remove_worktree(info)
    assert callbacks  # force-confirm alert shown
    with (
        patch("pigit.app.dismiss_sheet"),
        patch("pigit.app.show_toast"),
    ):
        callbacks[0](True)  # user confirms --force
    app._git.remove_worktree.assert_called_once_with("/dirty/wt", force=True)


def test_remove_clean_worktree_removes_without_force(runtime):
    app, _root = _mount(runtime)
    info = WorktreeInfo("/clean/wt", "aaa", "feat", False, False)
    app._git.is_worktree_dirty = Mock(return_value=False)
    app._git.remove_worktree = Mock()
    app.open_worktree_picker = Mock()
    callbacks: list[Callable] = []
    app._alert_dialog.alert = Mock(
        side_effect=lambda msg, cb, **kw: callbacks.append(cb)
    )
    with patch("pigit.app.show_toast"):
        app._confirm_remove_worktree(info)
    assert callbacks
    with (
        patch("pigit.app.dismiss_sheet"),
        patch("pigit.app.show_toast"),
    ):
        callbacks[0](True)
    app._git.remove_worktree.assert_called_once_with("/clean/wt", force=False)
