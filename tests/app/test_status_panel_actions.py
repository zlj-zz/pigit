# -*- coding: utf-8 -*-
"""
Module: tests/app/test_status_panel_actions.py
Description: StatusPanel a/d target resolution in tree view.
Author: Zev
Date: 2026-08-18
"""

from __future__ import annotations

import threading
import time

import pytest
from unittest.mock import Mock, patch

from pigit.app_status import StatusPanel
from pigit.termui import AsyncTask
from pigit.git.model import File
from pigit.termui.reactive import Signal
from pigit.viewmodels.base import ActionResult
from pigit.viewmodels.status import IStatusViewModel


@pytest.fixture(autouse=True)
def _inline_spinner(monkeypatch):
    """Run spinner-wrapped work inline so panel assertions stay synchronous."""

    def _run(work, on_done, *, label):
        on_done(work())
        return Mock()

    monkeypatch.setattr("pigit.app_status.run_with_spinner", _run)


def _file(
    name: str,
    *,
    short_status: str = " M",
    has_staged: bool = False,
    has_unstaged: bool = True,
    conflicts: bool = False,
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
        has_merged_conflicts=conflicts,
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


def test_checkout_ours_confirms_before_discarding_theirs() -> None:
    """Taking one side of a conflict destroys the other with no backup."""
    files = [_file("a.py", short_status="UU", conflicts=True)]
    panel, vm = _panel(files, tree=False)
    captured: dict = {}

    def fake_alert(text, on_result, kind=None):
        captured["text"] = text
        captured["on_result"] = on_result
        return True

    panel._alert_dialog.alert = fake_alert
    panel.checkout_ours()

    assert captured["text"] == "Discard theirs, keep ours in 'a.py' ?"
    vm.checkout_ours.assert_not_called()
    captured["on_result"](True)
    vm.checkout_ours.assert_called_once_with(0)


def test_checkout_ours_cancel_touches_nothing() -> None:
    files = [_file("a.py", short_status="UU", conflicts=True)]
    panel, vm = _panel(files, tree=False)
    captured: dict = {}
    panel._alert_dialog.alert = lambda text, on_result, kind=None: (
        captured.update(on_result=on_result) or True
    )

    panel.checkout_ours()
    captured["on_result"](False)
    vm.checkout_ours.assert_not_called()


def test_checkout_theirs_on_a_clean_file_does_not_confirm() -> None:
    """A non-conflicted row must not raise a dialog that leads nowhere."""
    files = [_file("a.py")]
    panel, vm = _panel(files, tree=False)
    alerts: list = []
    panel._alert_dialog.alert = lambda *a, **k: alerts.append(a) or True

    with patch("pigit.app_status.show_toast") as toast:
        panel.checkout_theirs()

    assert alerts == []
    vm.checkout_theirs.assert_not_called()
    assert toast.call_args[0][0] == "No conflicts"


def test_confirm_says_so_when_a_modal_blocks_the_dialog() -> None:
    """``alert`` returns False while another modal is open; the action then
    silently never runs, which is indistinguishable from a dead key."""
    files = [_file("a.py")]
    panel, _vm = _panel(files, tree=False)
    panel._alert_dialog.alert = lambda *a, **k: False

    with patch("pigit.app_status.show_toast") as toast:
        panel._confirm("Discard?", lambda _ok: None)

    assert toast.call_args[0][0] == "Close the open dialog first"


def test_stage_single_file_runs_through_the_worker() -> None:
    files = [_file("a.py")]
    panel, vm = _panel(files, tree=False)
    panel.curr_no = 0
    panel.stage()
    vm.stage.assert_called_once_with(0)


def test_ignore_on_dir_dispatches_child_indices() -> None:
    """Tree-mode ``i`` on a directory is its own entry point: it never goes
    through ``_run_action``, so it needs its own worker wrap."""
    files = [_file("src/a.py"), _file("src/b.py")]
    panel, vm = _panel(files)
    vm.ignore_indices.return_value = ActionResult(True, "ok", False)
    panel.curr_no = 0
    panel.ignore()
    vm.ignore_indices.assert_called_once_with({0, 1})


def test_ignore_visual_batch_runs_through_the_worker() -> None:
    """Visual mode with ``needs_confirm=False`` reaches ``_run_action``'s own
    batch branch — a third sync path, separate from the confirm helper."""
    files = [_file("a.py"), _file("b.py")]
    panel, vm = _panel(files, tree=False)
    vm.ignore_indices.return_value = ActionResult(True, "ok", False)
    panel._visual_mode = True
    panel._selected = {0, 1}

    panel.ignore()

    vm.ignore_indices.assert_called_once_with({0, 1})
    # Cleared in `after`, i.e. once the report has refreshed the list.
    assert panel._visual_mode is False


def test_ignore_single_file_runs_through_the_worker() -> None:
    """The non-confirm single path is a fourth entry of its own."""
    files = [_file("a.py")]
    panel, vm = _panel(files, tree=False)
    vm.ignore.return_value = ActionResult(True, "ok", False)
    panel.curr_no = 0
    panel.ignore()
    vm.ignore.assert_called_once_with(0)


def test_after_runs_only_once_the_result_has_been_reported() -> None:
    """``after`` reads the row list ``_handle_result`` just refreshed; running
    it first clears the selection against the stale list."""
    panel, _vm = _panel([_file("a.py")])
    order: list[str] = []
    panel._handle_result = lambda _result: order.append("report")

    panel._run_file_action(
        lambda: ActionResult(True, "ok", False),
        label="Staging",
        after=lambda: order.append("after"),
    )

    assert order == ["report", "after"]


def test_file_action_runs_off_the_ui_thread(monkeypatch, mocker) -> None:
    """End-to-end through the real ``run_with_spinner``: the VM call happens
    on a worker thread and the report lands on the main thread via poll_all."""
    from pigit.termui import run_with_spinner as real_spinner

    # This file's autouse fixture inlines the spinner; put the real one back.
    monkeypatch.setattr("pigit.app_status.run_with_spinner", real_spinner)
    mocker.patch("pigit.termui.overlay.show_spinner")
    mocker.patch("pigit.termui.overlay.hide_spinner")

    files = [_file("a.py"), _file("b.py"), _file("c.py")]
    panel, vm = _panel(files, tree=False)
    seen: dict = {}

    def _stage_all(_indices):
        seen["thread"] = threading.current_thread()
        return ActionResult(True, "Staged 3 file(s)", False)

    vm.stage_indices.side_effect = _stage_all
    reported: list[str] = []
    panel._handle_result = lambda result: reported.append(result.message)

    panel.stage_all()
    # The worker may already have started — what must not happen is the result
    # being applied here, on this thread.
    assert reported == []

    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline and not reported:
        AsyncTask.poll_all()
        time.sleep(0.01)

    assert seen["thread"] is not threading.main_thread()
    assert reported == ["Staged 3 file(s)"]


def test_worker_failure_names_the_action(monkeypatch, mocker) -> None:
    """AsyncTask reports a failure to the error callback, never to ``done``.
    Without the label the toast would not say which action died."""
    from pigit.termui import run_with_spinner as real_spinner

    monkeypatch.setattr("pigit.app_status.run_with_spinner", real_spinner)
    mocker.patch("pigit.termui.overlay.show_spinner")
    mocker.patch("pigit.termui.overlay.hide_spinner")
    toast = mocker.patch("pigit.termui.overlay.show_toast")

    panel, _vm = _panel([_file("a.py")], tree=False)

    def _boom(_idx):
        raise RuntimeError("index locked")

    panel._run_file_action(lambda: _boom(0), label="Staging")

    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline and not toast.called:
        AsyncTask.poll_all()
        time.sleep(0.01)

    assert toast.call_args[0][0] == "Staging failed: index locked"


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
