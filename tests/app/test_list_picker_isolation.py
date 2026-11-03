# -*- coding: utf-8 -*-
"""
Module: tests/app/test_list_picker_isolation.py
Description: Picker sheets keep Tab inside themselves and hand it back on close.
Author: Zev
Date: 2026-11-03
"""

from __future__ import annotations

import pytest

from pigit.app import PigitApplication
from pigit.app_repo_switcher import RepoSwitcherEntry, RepoSwitcherSheet
from pigit.config_data import AppConfig
from pigit.termui import show_sheet
from pigit.termui._runtime_context import (
    RuntimeContext,
    _runtime_ctx,
    set_overlay_host,
)
from pigit.termui.root import ComponentRoot


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


def _sheet() -> RepoSwitcherSheet:
    entries = [
        RepoSwitcherEntry(kind="repo", name=f"r{i}", path=f"/tmp/r{i}", meta={})
        for i in range(3)
    ]
    return RepoSwitcherSheet(entries=entries, on_switch=lambda _path: None)


def test_tab_moves_inside_the_sheet_and_not_the_panel_behind_it(runtime):
    """Tab is a panel key everywhere else. A sheet owns it while it is open --
    the sheet swallows what its child declines, so nothing leaks behind it."""
    app, root = _mount(runtime)
    panel_before = app._tab_view.visible
    sheet = _sheet()
    show_sheet(sheet, title_core="Switch repo", edge="bottom")

    root._handle_event("tab")

    assert root._focus_manager.get_focus_leaf() is sheet
    assert sheet.curr_no == 1
    assert app._tab_view.visible is panel_before


def test_tab_is_a_panel_key_again_once_the_sheet_closes(runtime):
    app, root = _mount(runtime)
    panel_before = app._tab_view.visible
    sheet = _sheet()
    show_sheet(sheet, title_core="Switch repo", edge="bottom")

    root._handle_event("enter")  # activates the first row and closes

    assert app._tab_view.visible is panel_before
    root._handle_event("tab")
    assert app._tab_view.visible is not panel_before
