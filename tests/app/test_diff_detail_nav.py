# -*- coding: utf-8 -*-
"""
Module: tests/app/test_diff_detail_nav.py
Description: Diff opens as BodyHost detail; Esc returns without TabView peer.
Author: Zev
Date: 2026-08-25
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from pigit.app import PigitApplication
from pigit.app_body_host import BodyHost
from pigit.app_diff import DiffViewer
from pigit.config_data import AppConfig
from pigit.termui import EVT_GOTO, Component, keys
from pigit.termui.root import ComponentRoot
from pigit.termui._runtime_context import RuntimeContext, _runtime_ctx


@pytest.fixture
def runtime():
    ctx = RuntimeContext()
    token = _runtime_ctx.set(ctx)
    yield ctx
    _runtime_ctx.reset(token)


def _mount(runtime: RuntimeContext) -> tuple[PigitApplication, ComponentRoot]:
    """Build the app tree and bind root key handlers without starting the loop."""
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
    root.activate()
    root.resize((80, 24))
    return app, root


def _leaf(root: ComponentRoot):
    return root._focus_manager.get_focus_leaf()


class _Box(Component):
    def __init__(self, id: str) -> None:
        super().__init__(id=id)
        self.deactivated = 0

    def deactivate(self) -> None:
        self.deactivated += 1
        super().deactivate()


def test_tab_view_has_no_diff_child(runtime):
    app, _root = _mount(runtime)
    ids = [c.id for c in app._tab_view.children]
    assert "diff" not in ids
    assert app._body_host.detail is app._diff_panel


def test_enter_opens_detail_via_bubbled_goto(runtime):
    """Status EVT_GOTO target=diff bubbles past TabView into Application."""
    app, root = _mount(runtime)
    with patch.object(app._status_panel._vm, "load_diff", return_value="+line\n"):
        app._status_panel._vm.files = MagicMock()
        hit = MagicMock()
        hit.name = "a.py"
        hit.has_staged_change = False
        hit.has_unstaged_change = True
        with patch.object(app._status_panel, "file_at_cursor", return_value=(hit, 0)):
            with patch.object(app._status_panel, "_tree_mode", False):
                app._status_panel.open_diff()

    assert app._body_host.is_detail_open is True
    assert _leaf(root) is app._diff_panel
    assert app._diff_panel.come_from is app._status_panel


def test_esc_closes_detail_and_restores_status(runtime):
    app, root = _mount(runtime)
    app._handle_body_goto(
        target="diff",
        source=app._status_panel,
        content=["+a"],
        key="a.py",
    )
    assert app._body_host.is_detail_open
    assert _leaf(root) is app._diff_panel

    root._handle_event(keys.KEY_ESC)
    assert not app._body_host.is_detail_open
    assert _leaf(root) is app._status_panel


def test_navigate_product_closes_detail(runtime):
    app, root = _mount(runtime)
    app._body_host.show_detail()
    assert app._body_host.is_detail_open
    app.navigate_product("branch")
    assert not app._body_host.is_detail_open
    assert app._tab_view.active is app._branch_panel
    assert _leaf(root) is app._branch_panel


def test_palette_has_no_diff_command():
    from pigit.app_command_palette import DEFAULT_COMMANDS, KNOWN_COMMAND_IDS

    assert "diff" not in KNOWN_COMMAND_IDS
    assert all(item.id != "diff" for item in DEFAULT_COMMANDS)


def test_reopen_detail_keeps_render_tokens_without_set_content():
    """Hide≠deactivate: Esc then show_detail must not clear tokens."""

    class _SpyDiff(DiffViewer):
        def __init__(self) -> None:
            super().__init__(id="diff")
            self.deactivated = 0
            self.paused = 0

        def deactivate(self) -> None:
            self.deactivated += 1
            super().deactivate()

        def pause_background(self) -> None:
            self.paused += 1
            super().pause_background()

    product = _Box("product")
    dv = _SpyDiff()
    dv._content = ["+a", "+b", "+c"]
    dv._render_tokens = [[("a", (1, 1, 1), 1, None)]] * 3
    host = BodyHost(product, dv, id="body")
    host.show_detail()
    host.show_product()
    host.show_detail()
    assert len(dv._render_tokens) == 3
    assert dv.deactivated == 0
    assert dv.paused == 1


def test_esc_from_commit_restores_header_tab(runtime):
    """Closing Diff on Commit must not leave header tab blank."""
    app, root = _mount(runtime)
    app._tab_view.route_to("commit")
    assert app._header_state.tab == "Commit"

    app._handle_body_goto(
        target="diff",
        source=app._commit_panel,
        content=["+a"],
        key="x",
    )
    assert app._header_state.tab == "Display"

    root._handle_event(keys.KEY_ESC)
    assert not app._body_host.is_detail_open
    assert app._header_state.tab == "Commit"
    assert _leaf(root) is app._commit_panel


def test_string_goto_while_detail_open_navigates_product(runtime):
    """Detail-open EVT_GOTO with a product id string must switch the tab."""
    app, root = _mount(runtime)
    app._handle_body_goto(
        target="diff",
        source=app._status_panel,
        content=["+a"],
        key="a.py",
    )
    assert app._body_host.is_detail_open

    assert app._handle_body_goto(target="commit") is True
    assert not app._body_host.is_detail_open
    assert app._tab_view.active is app._commit_panel
    assert _leaf(root) is app._commit_panel


def test_string_stash_goto_while_detail_open_focuses_stash(runtime):
    app, root = _mount(runtime)
    app._body_host.show_detail()
    assert app._handle_body_goto(target="stash") is True
    assert not app._body_host.is_detail_open
    assert _leaf(root) is app._stash_panel


def test_reveal_product_resyncs_split_widths_after_narrow_while_detail(runtime):
    """Closing Diff reapplies SplitPane widths for the current terminal."""
    app, root = _mount(runtime)
    root.resize((140, 24))
    app._is_large_screen = True
    app._apply_body_widths(140)
    assert "preview" in [c.id for c in app._split_pane.children]

    app._body_host.show_detail()
    app._is_large_screen = False
    # Mimic resize while detail open: early-return left stale large widths.
    app._split_pane._widths = [50, 90]

    app._reveal_product()
    assert not app._body_host.is_detail_open
    assert app._split_pane._widths == ["flex"]
    assert [c.id for c in app._split_pane.children] == ["tab_view"]


def test_pause_background_bumps_patch_gen_without_deactivate():
    dv = DiffViewer(id="diff")
    dv.activate()
    gen = dv._patch_gen
    tokens = [[("a", (1, 1, 1), 1, None)]]
    dv._render_tokens = tokens
    dv.pause_background()
    assert dv.is_activated()
    assert dv._patch_gen == gen + 1
    assert dv._render_tokens is tokens
