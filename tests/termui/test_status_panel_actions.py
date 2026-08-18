# -*- coding: utf-8 -*-
"""
Module: tests/termui/test_status_panel_actions.py
Description: StatusPanel a/d target resolution in tree view.
Author: Zev
Date: 2026-08-18
"""

from __future__ import annotations

from unittest.mock import Mock

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
    panel._filter.query = "a.py"
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

    def fake_alert(text, on_result, destructive=False):
        captured["text"] = text
        captured["on_result"] = on_result
        return True

    panel._alert_dialog.alert = fake_alert
    panel.discard()
    assert captured["text"] == "Discard 2 files?"
    vm.discard_indices.assert_not_called()
    captured["on_result"](True)
    vm.discard_indices.assert_called_once_with({0, 1})
