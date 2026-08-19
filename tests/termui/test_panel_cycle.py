# -*- coding: utf-8 -*-
"""
Module: tests/termui/test_panel_cycle.py
Description: App-level Status → Stash → Branch → Commit focus cycle.
Author: Zev
Date: 2026-08-18
"""

from __future__ import annotations

import pytest

from pigit.app import PigitApplication
from pigit.config_data import AppConfig
from pigit.termui import keys
from pigit.termui._root import ComponentRoot
from pigit.termui._runtime_context import RuntimeContext, _runtime_ctx


@pytest.fixture
def runtime():
    ctx = RuntimeContext()
    token = _runtime_ctx.set(ctx)
    yield ctx
    _runtime_ctx.reset(token)


def _mount(
    runtime: RuntimeContext, *, config: AppConfig | None = None
) -> tuple[PigitApplication, ComponentRoot]:
    """Build the app tree and bind root key handlers without starting the loop."""
    app = PigitApplication(config=config or AppConfig())
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


def test_help_lists_tab_cycle_and_numbered_goto():
    app = PigitApplication(config=AppConfig())
    entries = app.get_help_entries()
    by_key = {key: desc for key, desc in entries}
    assert "Tab" in by_key
    assert "Shift+Tab" in by_key
    assert by_key["1"].lower().find("status") >= 0
    assert by_key["2"].lower().find("stash") >= 0
    assert by_key["3"].lower().find("branch") >= 0
    assert by_key["4"].lower().find("commit") >= 0


def test_tab_cycles_status_stash_branch_commit(runtime):
    app, root = _mount(runtime)
    assert _leaf(root) is app._status_panel

    root._handle_event(keys.KEY_TAB)
    assert _leaf(root) is app._stash_panel

    root._handle_event(keys.KEY_TAB)
    assert _leaf(root) is app._branch_panel

    root._handle_event(keys.KEY_TAB)
    assert _leaf(root) is app._commit_panel

    root._handle_event(keys.KEY_TAB)
    assert _leaf(root) is app._status_panel


def test_shift_tab_cycles_backward(runtime):
    app, root = _mount(runtime)
    root._handle_event(keys.KEY_SHIFT_TAB)
    assert _leaf(root) is app._commit_panel
    root._handle_event(keys.KEY_SHIFT_TAB)
    assert _leaf(root) is app._branch_panel


def test_tab_on_diff_is_noop(runtime):
    app, root = _mount(runtime)
    app._tab_view.route_to("diff")
    assert _leaf(root) is app._diff_panel
    root._handle_event(keys.KEY_TAB)
    assert _leaf(root) is app._diff_panel
    root._handle_event(keys.KEY_SHIFT_TAB)
    assert _leaf(root) is app._diff_panel


def test_number_keys_land_on_four_panels(runtime):
    app, root = _mount(runtime)
    root._handle_event("2")
    assert _leaf(root) is app._stash_panel
    root._handle_event("3")
    assert _leaf(root) is app._branch_panel
    root._handle_event("4")
    assert _leaf(root) is app._commit_panel
    root._handle_event("1")
    assert _leaf(root) is app._status_panel


def test_filter_consumes_digit_before_panel_goto(runtime):
    """An active search filter gets digits before the app-level goto bindings."""
    app, root = _mount(runtime)
    app._status_panel.search()  # activate the filter
    assert app._status_panel._filter.active

    root._handle_event("4")
    assert app._status_panel._filter.query == "4"
    assert _leaf(root) is app._status_panel  # focus did not jump to Commit


def test_filter_absorbs_tab_without_cycling(runtime):
    """While the filter is active, Tab is absorbed and does not cycle panels."""
    app, root = _mount(runtime)
    app._status_panel.search()
    root._handle_event(keys.KEY_TAB)
    assert _leaf(root) is app._status_panel


def test_filter_exit_restores_number_goto(runtime):
    """Leaving the filter restores the '4' → Commit panel shortcut."""
    app, root = _mount(runtime)
    app._status_panel.search()
    root._handle_event(keys.KEY_ESC)
    assert not app._status_panel._filter.active

    root._handle_event("4")
    assert _leaf(root) is app._commit_panel


def _body_ids(app: PigitApplication) -> list[str | None]:
    return [child.id for child in app._body_row.children]


def test_large_screen_status_inserts_diff_preview_not_log_graph(runtime):
    app, _root = _mount(runtime)
    app._is_large_screen = True
    app._apply_body_widths(140)
    ids = _body_ids(app)
    assert "preview" in ids
    assert "log_graph_preview" not in ids


def test_large_screen_branch_inserts_log_graph_not_diff_preview(runtime):
    app, _root = _mount(runtime)
    app._is_large_screen = True
    app._tab_view.route_to("branch")
    app._apply_body_widths(140)
    ids = _body_ids(app)
    assert "log_graph_preview" in ids
    assert "preview" not in ids


def test_large_screen_commit_has_no_side_preview(runtime):
    app, _root = _mount(runtime)
    app._is_large_screen = True
    app._tab_view.route_to("commit")
    app._apply_body_widths(140)
    ids = _body_ids(app)
    assert "preview" not in ids
    assert "log_graph_preview" not in ids


def test_large_screen_stash_keeps_diff_preview(runtime):
    app, _root = _mount(runtime)
    app._is_large_screen = True
    app._tab_view.route_to("status")
    app._status_stack.set_focus_index(1)
    app._apply_body_widths(140)
    ids = _body_ids(app)
    assert "preview" in ids
    assert "log_graph_preview" not in ids


def test_status_to_branch_sizes_log_graph_preview(runtime, monkeypatch):
    """Status then Branch share the same width spec; the new panel must still be sized."""
    monkeypatch.setattr("pigit.app.terminal_size", lambda: (140, 24))
    app, root = _mount(runtime)
    app._is_large_screen = True
    root.resize((140, 24))
    app._apply_body_widths(140)
    assert app._preview_panel is not None
    assert app._preview_panel._size[0] > 0

    app._tab_view.route_to("branch")
    preview = app._log_graph_preview
    assert preview is not None
    assert preview._size[0] > 0
    assert preview._size[1] > 0
    assert preview._browser._size[0] > 0


def test_diff_preview_default_false_hides_on_large_screen(runtime) -> None:
    app, _root = _mount(runtime, config=AppConfig(diff_preview_default=False))
    app._is_large_screen = True
    app._apply_body_widths(140)
    assert "preview" not in _body_ids(app)


def test_log_graph_default_false_hides_on_large_screen(runtime) -> None:
    app, _root = _mount(runtime, config=AppConfig(log_graph_default=False))
    app._is_large_screen = True
    app._tab_view.route_to("branch")
    app._apply_body_widths(140)
    assert "log_graph_preview" not in _body_ids(app)


def test_ctrl_p_toggles_diff_preview_on_large_screen(runtime, monkeypatch) -> None:
    monkeypatch.setattr("pigit.app.terminal_size", lambda: (140, 24))
    app, root = _mount(runtime)
    app._is_large_screen = True
    app._apply_body_widths(140)
    assert "preview" in _body_ids(app)

    root._handle_event("ctrl p")
    assert "preview" not in _body_ids(app)

    root._handle_event("ctrl p")
    assert "preview" in _body_ids(app)


def test_ctrl_p_on_stash_toggles_diff_preview(runtime, monkeypatch) -> None:
    monkeypatch.setattr("pigit.app.terminal_size", lambda: (140, 24))
    app, root = _mount(runtime)
    app._is_large_screen = True
    root._handle_event("2")
    app._apply_body_widths(140)
    assert "preview" in _body_ids(app)

    root._handle_event("ctrl p")
    assert "preview" not in _body_ids(app)
    assert app._diff_preview_wanted is False


def test_ctrl_p_toggles_branch_log_graph_on_large_screen(runtime, monkeypatch) -> None:
    monkeypatch.setattr("pigit.app.terminal_size", lambda: (140, 24))
    app, root = _mount(runtime)
    app._is_large_screen = True
    root._handle_event("3")
    app._apply_body_widths(140)
    assert "log_graph_preview" in _body_ids(app)
    diff_wanted = app._diff_preview_wanted

    root._handle_event("ctrl p")
    assert "log_graph_preview" not in _body_ids(app)
    assert app._diff_preview_wanted is diff_wanted

    root._handle_event("ctrl p")
    assert "log_graph_preview" in _body_ids(app)


def test_ctrl_p_on_commit_does_not_toggle_previews(runtime, monkeypatch) -> None:
    monkeypatch.setattr("pigit.app.terminal_size", lambda: (140, 24))
    app, root = _mount(runtime)
    app._is_large_screen = True
    app._apply_body_widths(140)
    diff_wanted = app._diff_preview_wanted
    log_graph_wanted = app._log_graph_wanted

    root._handle_event("4")
    app._apply_body_widths(140)
    root._handle_event("ctrl p")

    assert app._diff_preview_wanted is diff_wanted
    assert app._log_graph_wanted is log_graph_wanted
    assert "preview" not in _body_ids(app)
    assert "log_graph_preview" not in _body_ids(app)


def test_ctrl_p_on_narrow_terminal_toasts_and_keeps_hidden(
    runtime, monkeypatch
) -> None:
    monkeypatch.setattr("pigit.app.terminal_size", lambda: (80, 24))
    toasts: list[str] = []
    monkeypatch.setattr(
        "pigit.app.show_toast", lambda msg, **_kwargs: toasts.append(msg)
    )
    app, root = _mount(runtime)
    assert app._is_large_screen is False
    assert "preview" not in _body_ids(app)
    wanted = app._diff_preview_wanted

    root._handle_event("ctrl p")

    assert "preview" not in _body_ids(app)
    assert app._diff_preview_wanted is wanted
    assert toasts
    assert "120" in toasts[0]


def test_diff_and_log_graph_toggles_are_independent(runtime, monkeypatch) -> None:
    monkeypatch.setattr("pigit.app.terminal_size", lambda: (140, 24))
    app, root = _mount(runtime)
    app._is_large_screen = True
    app._apply_body_widths(140)

    root._handle_event("ctrl p")
    assert app._diff_preview_wanted is False

    root._handle_event("3")
    app._apply_body_widths(140)
    assert "log_graph_preview" in _body_ids(app)

    root._handle_event("ctrl p")
    assert "log_graph_preview" not in _body_ids(app)
    assert app._diff_preview_wanted is False

    root._handle_event("1")
    app._apply_body_widths(140)
    assert "preview" not in _body_ids(app)


def test_help_lists_ctrl_p_on_preview_panels_not_global(runtime) -> None:
    app, _root = _mount(runtime)
    global_keys = {key for key, _ in app.get_help_entries()}
    assert "Ctrl+p" not in global_keys
    assert "Ctrl+P" not in global_keys

    status = {key: desc for key, desc in app._status_panel.get_help_entries()}
    assert "Ctrl+p" in status
    assert "preview" in status["Ctrl+p"].lower()

    stash = {key: desc for key, desc in app._stash_panel.get_help_entries()}
    assert "Ctrl+p" in stash
    assert "preview" in stash["Ctrl+p"].lower()

    branch = {key: desc for key, desc in app._branch_panel.get_help_entries()}
    assert "Ctrl+p" in branch
    assert "preview" in branch["Ctrl+p"].lower()

    commit = {key: desc for key, desc in app._commit_panel.get_help_entries()}
    assert "Ctrl+p" not in commit
    assert "Ctrl+r" in commit
    assert "report" in commit["Ctrl+r"].lower()
