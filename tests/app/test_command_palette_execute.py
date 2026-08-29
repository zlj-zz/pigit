"""
Module: tests/app/test_command_palette_execute.py
Description: App-level command palette execute routing.
Author: Zev
Date: 2026-08-21
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from pigit.app import PigitApplication
from pigit.config_data import AppConfig
from pigit.termui import FeedbackKind
from pigit.viewmodels.base import ActionResult


@pytest.fixture
def app():
    application = PigitApplication(config=AppConfig())
    application._git = MagicMock()
    application._root = MagicMock()
    application._branch_vm = MagicMock()
    application._status_vm = MagicMock()
    from pigit.termui.reactive import Signal

    application._branch_vm.items = Signal([])
    application._status_vm.items = Signal([])
    return application


def test_unknown_command_toasts(app):
    with patch("pigit.app.show_toast") as toast:
        app._on_palette_execute("not-a-real-command")
    toast.assert_called_once()
    assert "Unknown command" in toast.call_args[0][0]
    assert toast.call_args[1]["kind"] is FeedbackKind.WARNING


def test_stash_focuses_stash_panel(app):
    with patch.object(app, "goto_stash") as goto:
        app._on_palette_execute("stash")
    goto.assert_called_once()


def test_toggle_palette_sets_slots_from_root_and_opens_sheet(app):
    from pigit.app_command_palette import CommandPalette
    from pigit.termui.reactive import Signal
    from pigit.termui.widgets.command_palette import list_slots_for_term
    from pigit.termui.widgets.sheet import Sheet

    app._palette = CommandPalette(
        on_execute=app._on_palette_execute,
        on_dismiss=app._dismiss_palette,
    )
    app._git.sequencer_in_progress.return_value = None
    app._root._size = (120, 40)
    app._branch_vm.items = Signal(
        [SimpleNamespace(name="main"), SimpleNamespace(name="dev")]
    )
    app._status_vm.items = Signal([SimpleNamespace(get_file_str=lambda: "a.py")])

    app.toggle_palette()

    expected_slots = list_slots_for_term(40)
    assert app._palette._list_slots == expected_slots
    ids = [i.id for i in app._palette._items]
    assert "checkout" in ids
    assert "stage" in ids
    assert "status" in ids
    app._branch_vm.refresh.assert_called_once()
    app._status_vm.refresh.assert_called_once()
    assert len(app._palette_vm_unsubs) == 2
    app._root.show_sheet.assert_called_once()
    args, kwargs = app._root.show_sheet.call_args
    assert args == (app._palette,)
    assert "height" not in kwargs
    assert kwargs.get("title") == "Commands"
    assert kwargs.get("show_edge_rule", True) is True
    assert kwargs.get("bg") is None
    assert (
        Sheet.resolve_height(app._palette, 40) == app._palette.preferred_sheet_height()
    )


def test_toggle_palette_refresh_candidates_when_branch_items_update(app):
    from pigit.app_command_palette import CommandPalette
    from pigit.termui import keys
    from pigit.termui.reactive import Signal

    app._palette = CommandPalette(
        on_execute=app._on_palette_execute,
        on_dismiss=app._dismiss_palette,
    )
    app._git.sequencer_in_progress.return_value = None
    app._root._size = (120, 40)
    app._branch_vm.items = Signal([])
    app._status_vm.items = Signal([])

    app.toggle_palette()
    for ch in "checkout ":
        app._palette.handle_key(ch)
    assert app._palette._arg_mode == "checkout"
    assert app._palette._matched == []

    with patch("pigit.termui.widgets.command_palette.request_render") as render:
        app._branch_vm.items.set([SimpleNamespace(name="dev")])
        render.assert_called()
    assert [c.id for c in app._palette._matched] == ["checkout dev"]

    app._palette.handle_key(keys.KEY_ESC)
    assert app._palette_vm_unsubs == []
    assert not app._palette.is_active


def test_catalog_hides_sequencer_when_idle():
    from pigit.app_command_palette import catalog_for_context

    ids = [i.id for i in catalog_for_context(None)]
    assert "status" in ids
    assert "diff" not in ids
    assert "continue-merge" not in ids
    assert "rebase-continue" not in ids
    assert "cherry-pick-abort" not in ids


def test_catalog_includes_rebase_when_active():
    from pigit.app_command_palette import catalog_for_context

    ids = [i.id for i in catalog_for_context("rebase")]
    assert "rebase-continue" in ids
    assert "cherry-pick-continue" not in ids


def test_build_catalog_injects_parameterized_and_filters_static():
    from pigit.app_command_palette import build_catalog

    catalog = build_catalog(
        None,
        branch_names=lambda: ["main", "feature"],
        file_names=lambda: ["a.py", "b.py"],
    )
    by_id = {i.id: i for i in catalog}
    assert "continue-merge" not in by_id
    assert by_id["checkout"].args is not None
    assert by_id["checkout"].args.fetch("fea") == ["feature"]
    assert by_id["stage"].args.fetch("a") == ["a.py"]


def test_checkout_resolves_exact_index_and_refreshes(app):
    branches = [
        SimpleNamespace(name="main"),
        SimpleNamespace(name="dev"),
        SimpleNamespace(name="develop"),
    ]
    app._branch_vm.items = SimpleNamespace(value=branches)
    app._branch_vm.checkout.return_value = ActionResult(
        success=True, message="Switched to dev", should_refresh=True
    )
    with (
        patch("pigit.app.show_toast") as toast,
        patch.object(app, "_refresh_git_vms") as refresh,
        patch.object(app, "_schedule_reload_header") as reload,
    ):
        app._on_palette_execute("checkout dev")
    app._branch_vm.checkout.assert_called_once_with(1)
    toast.assert_called_once()
    assert "Switched to dev" in toast.call_args[0][0]
    refresh.assert_called_once()
    reload.assert_called_once()


def test_checkout_double_space_strips_arg(app):
    branches = [
        SimpleNamespace(name="main"),
        SimpleNamespace(name="dev"),
    ]
    app._branch_vm.items = SimpleNamespace(value=branches)
    app._branch_vm.checkout.return_value = ActionResult(
        success=True, message="Switched to dev", should_refresh=False
    )
    with patch("pigit.app.show_toast"):
        app._on_palette_execute("checkout  dev")
    app._branch_vm.checkout.assert_called_once_with(1)


def test_checkout_no_exact_match_toasts_not_substring(app):
    branches = [
        SimpleNamespace(name="main"),
        SimpleNamespace(name="develop"),
    ]
    app._branch_vm.items = SimpleNamespace(value=branches)
    with patch("pigit.app.show_toast") as toast:
        app._on_palette_execute("checkout dev")
    app._branch_vm.checkout.assert_not_called()
    toast.assert_called_once()
    assert toast.call_args[0][0] == "No matching branch: dev"
    assert toast.call_args[1]["kind"] is FeedbackKind.WARNING


def test_checkout_empty_arg_toasts(app):
    app._branch_vm.items = SimpleNamespace(value=[SimpleNamespace(name="main")])
    with patch("pigit.app.show_toast") as toast:
        app._on_palette_execute("checkout")
    assert toast.call_args[0][0] == "No matching branch: "


def test_merge_routes_to_merge_request(app):
    app._branch_vm.items = SimpleNamespace(
        value=[SimpleNamespace(name="feature"), SimpleNamespace(name="main")]
    )
    app._branch_vm.current_branch.return_value = "main"
    with patch.object(app, "_on_merge_request") as merge:
        app._on_palette_execute("merge feature")
    merge.assert_called_once_with("feature", "main")


def test_stage_already_staged_toasts(app):
    files = [SimpleNamespace(get_file_str=lambda: "a.py")]
    app._status_vm.items = SimpleNamespace(value=files)
    app._status_vm.needs_stage.return_value = False
    with patch("pigit.app.show_toast") as toast:
        app._on_palette_execute("stage a.py")
    app._status_vm.stage.assert_not_called()
    assert toast.call_args[0][0] == "already staged"


def test_stage_unstaged_calls_vm(app):
    files = [SimpleNamespace(get_file_str=lambda: "a.py")]
    app._status_vm.items = SimpleNamespace(value=files)
    app._status_vm.needs_stage.return_value = True
    app._status_vm.stage.return_value = ActionResult(
        success=True, message="Staged a.py", should_refresh=True
    )
    with (
        patch("pigit.app.show_toast"),
        patch.object(app, "_refresh_git_vms") as refresh,
        patch.object(app, "_schedule_reload_header"),
    ):
        app._on_palette_execute("stage a.py")
    app._status_vm.stage.assert_called_once_with(0)
    refresh.assert_called_once()


def test_gitignore_calls_ignore(app):
    files = [SimpleNamespace(get_file_str=lambda: "tmp.log")]
    app._status_vm.items = SimpleNamespace(value=files)
    app._status_vm.ignore.return_value = ActionResult(
        success=True, message="Ignored tmp.log", should_refresh=True
    )
    with (
        patch("pigit.app.show_toast"),
        patch.object(app, "_refresh_git_vms") as refresh,
        patch.object(app, "_schedule_reload_header"),
    ):
        app._on_palette_execute("gitignore tmp.log")
    app._status_vm.ignore.assert_called_once_with(0)
    refresh.assert_called_once()


def test_static_commands_still_work_after_parameterized(app):
    with patch.object(app, "navigate_product") as nav:
        app._on_palette_execute("status")
    nav.assert_called_once_with("status")
