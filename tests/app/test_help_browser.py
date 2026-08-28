"""
Module: tests/app/test_help_browser.py
Description: App Help BindingBrowser open / actions / invoke wiring.
Author: Zev
Date: 2026-08-27
"""

from __future__ import annotations

from dataclasses import replace
from unittest.mock import MagicMock

import pytest

from pigit.app import PigitApplication
from pigit.config_data import AppConfig
from pigit.termui.root import ComponentRoot
from pigit.termui.widgets import BindingBrowser
from pigit.termui._runtime_context import RuntimeContext, _runtime_ctx
from pigit.termui.surface import Surface
from pigit.termui import by_id


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
    app.setup_root(root)
    root.mount()
    root.resize((100, 30))
    app._help_popup.resize((100, 30))
    return app, root


def test_setup_uses_binding_browser(runtime):
    app, _root = _mount(runtime)
    assert isinstance(app._help_browser, BindingBrowser)
    assert app._help_popup._child is app._help_browser


def test_help_groups_are_executable_bindings(runtime):
    app, _root = _mount(runtime)
    groups = app.get_help_groups()
    assert groups
    _title, entries = groups[0]
    assert entries
    assert hasattr(entries[0], "invoke")
    assert hasattr(entries[0], "action")


def test_toggle_help_opens_and_closes(runtime):
    app, _root = _mount(runtime)
    assert app._help_popup.open is False
    app.toggle_help()
    assert app._help_popup.open is True
    app.toggle_help()
    assert app._help_popup.open is False


def test_enter_invokes_after_close(runtime):
    app, _root = _mount(runtime)
    app.toggle_help()
    mock_fn = MagicMock()
    row = app._help_browser._selectable[0]
    app._help_browser._selectable[0] = replace(row, invoke=mock_fn)
    app._help_browser._cursor = 0
    app._help_browser.activate_selected()
    assert app._help_popup.open is False
    mock_fn.assert_called_once()


def test_enter_on_help_dismiss_only(runtime):
    app, _root = _mount(runtime)
    app.toggle_help()
    help_i = next(
        i
        for i, row in enumerate(app._help_browser._selectable)
        if row.action.endswith(".help")
    )
    app._help_browser._cursor = help_i
    app._help_browser.activate_selected()
    assert app._help_popup.open is False


def test_footer_shows_help_keys_without_global(runtime):
    app, _root = _mount(runtime)
    footer = by_id("footer")
    app.toggle_help()
    surface = Surface(100, 2)
    footer.resize((100, 2))
    footer.paint(surface)
    content = surface.lines()[1]
    assert "Navigate" in content
    assert "Run" in content
    assert "Close" in content
    assert "Quit" not in content
    assert "Palette" not in content
