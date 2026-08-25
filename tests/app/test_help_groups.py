# -*- coding: utf-8 -*-
"""
Module: tests/app/test_help_groups.py
Description: Help shows only the active panel group, then Global.
Author: Zev
Date: 2026-08-21
"""

from __future__ import annotations

import pytest

from pigit.app import PigitApplication
from pigit.config_data import AppConfig
from pigit.termui.root import ComponentRoot
from pigit.termui._runtime_context import RuntimeContext, _runtime_ctx


@pytest.fixture
def runtime():
    ctx = RuntimeContext()
    token = _runtime_ctx.set(ctx)
    yield ctx
    _runtime_ctx.reset(token)


def _mount(runtime: RuntimeContext) -> tuple[PigitApplication, ComponentRoot]:
    app = PigitApplication(config=AppConfig())
    body = app.build_root()
    root = ComponentRoot(
        body,
        runtime.registry,
        event_bus=app._event_bus,
        key_handlers=app._key_handlers,
    )
    runtime.overlay_host = root
    runtime.focus_manager = root._focus_manager
    root._app_on_event = app.on_event
    app._root = root
    root.mount()
    root.resize((80, 24))
    return app, root


def test_help_groups_status_then_global(runtime):
    app, _root = _mount(runtime)
    titles = [title for title, _entries in app.get_help_groups()]
    assert titles == [app._status_panel.get_help_title(), "Global"]


def test_help_groups_follow_active_panel_only(runtime):
    app, _root = _mount(runtime)
    app._focus_destination(app._branch_panel)
    titles = [title for title, _entries in app.get_help_groups()]
    assert titles == [app._branch_panel.get_help_title(), "Global"]
    assert app._status_panel.get_help_title() not in titles
    assert app._commit_panel.get_help_title() not in titles


def test_help_groups_stash_when_stash_focused(runtime):
    app, _root = _mount(runtime)
    app._focus_destination(app._stash_panel)
    titles = [title for title, _entries in app.get_help_groups()]
    assert titles == [app._stash_panel.get_help_title(), "Global"]
