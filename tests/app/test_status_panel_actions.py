# -*- coding: utf-8 -*-
"""
Module: tests/app/test_status_panel_actions.py
Description: StatusPanel a/d target resolution in tree view.
Author: Zev
Date: 2026-08-18
"""

from __future__ import annotations

from unittest.mock import Mock, patch

from pigit.app_status import StatusPanel
from pigit.git.model import File
from pigit.termui.reactive import Signal
from pigit.viewmodels.base import ActionResult
from pigit.viewmodels.status import IStatusViewModel


def _file(
    name: str,
    *,
    short_status: str = " M",
    has_staged: bool = False,
    has_unstaged: bool = True,
) -> File:
    return File(
        name=name,
        display_str=name,
        short_status=short_status,
        has_staged_change=has_staged,
        has_unstaged_change=has_unstaged,
        tracked=True,
        deleted=False,
        added=False,
        has_merged_conflicts=False,
        has_inline_merged_conflicts=False,
    )


def _panel(files: list[File], *, tree: bool = True) -> tuple[StatusPanel, Mock]:
    vm = Mock(spec=IStatusViewModel)
    vm.items = Signal(files)
    vm.repo_path = "/tmp/repo"
    ok = ActionResult(success=True, message="ok", should_refresh=False)
    vm.stage.return_value = ok
    vm.discard.return_value = ok
    vm.stage_indices.return_value = ok
    vm.discard_indices.return_value = ok
    panel = StatusPanel(vm=vm, default_view="tree" if tree else "flat")
    panel._all_files = list(files)
    panel._apply_filter()
    return panel, vm


def test_target_indices_dir_uses_child_indices() -> None:
    files = [_file("src/a.py"), _file("src/b.py"), _file("README.md")]
    panel, _vm = _panel(files)
    panel.curr_no = 0
    assert panel._row(0) is not None and panel._row(0).kind == "dir"
    assert panel._target_indices() == set(panel._row(0).child_indices) == {0, 1}


def test_target_indices_collapsed_dir_still_has_children() -> None:
    files = [_file("src/a.py"), _file("src/deep/b.py")]
    panel, _vm = _panel(files)
    panel._collapsed_dirs.add("src")
    panel._apply_filter()
    panel.curr_no = 0
    assert panel._row(0).path == "src"
    assert panel._target_indices() == {0, 1}


def test_target_indices_filter_limits_dir_children() -> None:
    files = [_file("src/a.py"), _file("src/b.py")]
    panel, _vm = _panel(files)
    panel._search_query = "a.py"
    panel._apply_filter()
    panel.curr_no = 0
    assert panel._target_indices() == {0}


def test_target_indices_visual_empty_does_not_use_dir() -> None:
    files = [_file("src/a.py"), _file("src/b.py")]
    panel, _vm = _panel(files)
    panel.curr_no = 0
    panel._visual_mode = True
    panel._selected = set()
    assert panel._target_indices() == set()


def test_target_indices_flat_file() -> None:
    files = [_file("a.py"), _file("b.py")]
    panel, _vm = _panel(files, tree=False)
    panel.curr_no = 1
    assert panel._target_indices() == {1}


def test_stage_on_dir_dispatches_child_indices() -> None:
    files = [_file("src/a.py"), _file("src/b.py")]
    panel, vm = _panel(files)
    panel.curr_no = 0
    panel.stage()
    vm.stage_indices.assert_called_once_with({0, 1})
    vm.stage.assert_not_called()


def test_discard_on_dir_confirms_then_discards_children() -> None:
    files = [_file("src/a.py"), _file("src/b.py")]
    panel, vm = _panel(files)
    panel.curr_no = 0
    captured: dict = {}

    def fake_alert(text, on_result, kind=None):
        captured["text"] = text
        captured["on_result"] = on_result
        return True

    panel._alert_dialog.alert = fake_alert
    panel.discard()
    assert captured["text"] == "Discard 2 files?"
    vm.discard_indices.assert_not_called()
    captured["on_result"](True)
    vm.discard_indices.assert_called_once_with({0, 1})


def test_stage_all_stages_every_listed_file() -> None:
    files = [_file("a.py"), _file("b.py"), _file("c.py")]
    panel, vm = _panel(files, tree=False)
    panel.stage_all()
    vm.stage_indices.assert_called_once_with({0, 1, 2})
    vm.stage.assert_not_called()


def test_stage_all_uses_filter_map() -> None:
    files = [_file("src/a.py"), _file("src/b.py"), _file("README.md")]
    panel, vm = _panel(files)
    panel._search_query = "src"
    panel._apply_filter()
    panel.stage_all()
    vm.stage_indices.assert_called_once_with({0, 1})


def test_stage_all_empty_is_noop() -> None:
    panel, vm = _panel([])
    panel.stage_all()
    vm.stage_indices.assert_not_called()


def test_help_stage_all_is_a_amend_is_m() -> None:
    panel, _vm = _panel([_file("a.py")])
    by_key = {k: d for k, d in panel.get_help_entries()}
    assert "all listed" in by_key["A"].lower()
    assert "amend" in by_key["m"].lower()
    assert "amend" not in by_key["A"].lower()


def test_stash_opens_message_sheet_without_pushing() -> None:
    files = [_file("a.py")]
    panel, vm = _panel(files)
    with patch("pigit.app_status.show_sheet") as sheet:
        panel.stash()
        sheet.assert_called_once()
        vm.stash_push.assert_not_called()


def test_stash_submit_strips_message_and_pushes() -> None:
    files = [_file("a.py")]
    panel, vm = _panel(files)
    vm.stash_push.return_value = ActionResult(
        success=True, message="Stashed", should_refresh=True
    )
    with (
        patch("pigit.app_status.dismiss_sheet") as dismiss,
        patch("pigit.app_status.show_badge"),
    ):
        panel._on_stash_submit("  wip  ")
        dismiss.assert_called_once()
        vm.stash_push.assert_called_once_with("wip")


def test_file_icon_name_prefix_when_enabled_and_fallback() -> None:
    """nerd_icons=True prefixes the name with a Nerd Font icon; False uses
    the 1-cell fallback symbol (never blank)."""
    from pigit.ext.utils import adjudgment_type, get_file_icon, resolve_icon

    vm = Mock(spec=IStatusViewModel)
    vm.items = Signal([_file("main.py")])
    vm.repo_path = "/tmp/repo"
    file = _file("main.py")

    panel = StatusPanel(vm=vm, default_view="flat", nerd_icons=True)
    panel.files = [file]
    panel.set_content(["main.py"])
    left, main, _right = panel.describe_row(0, False)
    assert main[0].text == get_file_icon(adjudgment_type("main.py")) + " main.py"
    # Icon moved out of the leading status column.
    assert left[0].text == " "
    assert left[2].text == "M"  # unstaged column

    panel_off = StatusPanel(vm=vm, default_view="flat", nerd_icons=False)
    panel_off.files = [file]
    panel_off.set_content(["main.py"])
    _left, main_off, _r = panel_off.describe_row(0, False)
    fallback = resolve_icon(False, adjudgment_type("main.py"))
    assert main_off[0].text == f"{fallback} main.py"


def test_clean_tree_refresh_completion_clears_loading() -> None:
    """A clean tree refresh re-sets items to the same [] — Signal.set skips
    unchanged values, so the VM must force-notify on load completion or
    loading sticks on skeleton bars forever."""
    from pigit.termui.surface import Surface

    vm = Mock(spec=IStatusViewModel)
    vm.items = Signal([])
    vm.refresh = Mock()
    panel = StatusPanel(vm=vm)
    panel.unmount()
    panel.resize((44, 12))
    assert panel.loading is True

    panel.mount()
    # Async refresh is in flight: skeleton stays until the VM delivers.
    assert panel.loading is True

    # Load completes with the same empty list — force notify wakes the panel.
    vm.items.set([], force=True)
    assert panel.loading is False

    s = Surface(44, 12)
    panel.paint(s)
    text = "\n".join(s.lines())
    assert "Working tree clean" in text


def test_remount_requests_reload_and_skeleton() -> None:
    """Remounting kicks a fresh async refresh; skeleton shows until the VM
    force-notifies the (possibly unchanged) result."""
    vm = Mock(spec=IStatusViewModel)
    vm.items = Signal([])
    vm.refresh = Mock()
    panel = StatusPanel(vm=vm)
    panel.mount()
    assert panel.loading is True

    panel.mount()
    assert panel.loading is True  # fresh request in flight
    vm.items.set([], force=True)
    assert panel.loading is False


def test_stash_submit_empty_message_still_pushes() -> None:
    files = [_file("a.py")]
    panel, vm = _panel(files)
    vm.stash_push.return_value = ActionResult(
        success=True, message="Stashed", should_refresh=False
    )
    with (
        patch("pigit.app_status.dismiss_sheet"),
        patch("pigit.app_status.show_badge"),
    ):
        panel._on_stash_submit("   ")
        vm.stash_push.assert_called_once_with("")


def test_status_panel_receives_resolved_nerd_icons() -> None:
    """app.py wires config.icons through resolve_nerd_icons to StatusPanel."""
    from pigit.app import PigitApplication
    from pigit.config_data import AppConfig

    app_off = PigitApplication(config=AppConfig(icons="off", repo_observe=False))
    app_off.build_root()
    assert app_off._status_panel._nerd_icons is False

    app_on = PigitApplication(config=AppConfig(icons="on", repo_observe=False))
    app_on.build_root()
    assert app_on._status_panel._nerd_icons is True

    with patch("pigit.app.resolve_nerd_icons", return_value=True) as detect:
        app_auto = PigitApplication(config=AppConfig(icons="auto", repo_observe=False))
        app_auto.build_root()
    detect.assert_called_once_with("auto")
    assert app_auto._status_panel._nerd_icons is True
