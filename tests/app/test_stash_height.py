# -*- coding: utf-8 -*-
"""
Module: tests/app/test_stash_height.py
Description: Stash panel height follows its content — its floor when empty.
Author: Zev
Date: 2026-10-06
"""

from __future__ import annotations

from unittest.mock import Mock

from pigit.app import PigitApplication
from pigit.app_stash import StashPanel
from pigit.config_data import AppConfig
from pigit.git.model import Stash
from pigit.viewmodels.status import IStatusViewModel


def _app() -> PigitApplication:
    app = PigitApplication(config=AppConfig(repo_observe=False))
    app.build_root()
    return app


def _height(app: PigitApplication) -> int:
    return app._status_stack._heights[1]


def _stash(msg: str = "wip") -> Stash:
    return Stash(ref="stash@{0}", sha="a1b2c3d4", msg=msg)


def test_empty_stash_takes_only_its_floor():
    app = _app()
    app._stash_panel.stashes = []
    app._sync_stash_height(40)
    assert _height(app) == app.STASH_MIN_ROWS


def test_populated_stash_keeps_its_share():
    """A quarter of 20 is 5 -- under the cap, so this pins the formula itself."""
    app = _app()
    app._stash_panel.stashes = [_stash()]
    app._sync_stash_height(20)
    assert _height(app) == 5


def test_populated_stash_is_capped():
    app = _app()
    app._stash_panel.stashes = [_stash()]
    app._sync_stash_height(100)
    assert _height(app) == app.STASH_MAX_ROWS


def test_short_terminal_is_the_floor_either_way():
    """At 12 rows a quarter is already the floor, so emptying costs nothing."""
    app = _app()
    app._sync_stash_height(12)
    assert _height(app) == app.STASH_MIN_ROWS
    app._stash_panel.stashes = [_stash()]
    app._sync_stash_height(12)
    assert _height(app) == app.STASH_MIN_ROWS


def test_build_root_wires_the_refit_hook():
    """The one line that connects the panel to the re-fit, asserted directly."""
    app = _app()
    assert app._stash_panel._on_items_changed == app._on_stash_items_changed


def test_a_load_refits_the_height_through_the_app(monkeypatch):
    """End to end over the seam: load stashes -> the panel grows, no manual call."""
    monkeypatch.setattr("pigit.app.terminal_size", lambda: (100, 20))
    app = _app()
    app._sync_stash_height(20)
    assert _height(app) == app.STASH_MIN_ROWS  # nothing loaded yet

    vm = Mock(spec=IStatusViewModel)
    vm.load_stashes.return_value = [_stash()]
    app._stash_panel._vm = vm
    app._stash_panel._load_stashes()
    assert _height(app) == 5


def test_one_empty_to_full_transition_loads_once(monkeypatch):
    """The re-fit resizes the panel, and a resize reloads it. The load that is
    already running wins, or every transition runs ``git stash list`` twice."""
    monkeypatch.setattr("pigit.app.terminal_size", lambda: (100, 30))
    app = _app()
    vm = Mock(spec=IStatusViewModel)
    vm.load_stashes.return_value = []
    panel = app._stash_panel
    panel._vm = vm
    panel.resize((100, app.STASH_MIN_ROWS))  # give the panel a size
    app._status_stack.resize((100, 30))  # so a height change cascades
    app._sync_stash_height(30)
    assert _height(app) == app.STASH_MIN_ROWS

    vm.load_stashes.return_value = [_stash()]
    vm.load_stashes.reset_mock()
    panel._load_stashes()
    assert vm.load_stashes.call_count == 1
    assert _height(app) == 7  # a quarter of 30 -- and the height did move


class TestReloadNotifiesTheApp:
    """An empty list emits no ``EVT_SELECTION_CHANGED``, so the hook is the
    only way the app learns the panel went from full to empty or back."""

    def _panel(self, vm: Mock):
        seen: list[bool] = []
        panel = StashPanel(vm=vm, on_items_changed=lambda: seen.append(panel.is_empty()))
        return panel, seen

    def test_loaded_list(self):
        vm = Mock(spec=IStatusViewModel)
        vm.load_stashes.return_value = [
            Stash(ref="stash@{0}", sha="a1b2c3d4", msg="wip")
        ]
        panel, seen = self._panel(vm)
        panel._load_stashes()
        assert seen == [False]
        assert panel.is_empty() is False

    def test_emptied_list(self):
        vm = Mock(spec=IStatusViewModel)
        vm.load_stashes.return_value = []
        panel, seen = self._panel(vm)
        panel._load_stashes()
        assert seen == [True]

    def test_failed_load(self):
        vm = Mock(spec=IStatusViewModel)
        vm.load_stashes.side_effect = RuntimeError("boom")
        panel, seen = self._panel(vm)
        panel._load_stashes()
        assert seen == [True]
