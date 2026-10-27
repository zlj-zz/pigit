# -*- coding: utf-8 -*-
"""
Module: tests/app/test_panel_cycle.py
Description: App-level Status → Stash → Branch → Commit focus cycle.
Author: Zev
Date: 2026-08-18
"""

from __future__ import annotations

import pytest

from pigit.app import PigitApplication
from pigit.config_data import AppConfig
from pigit.git.model import Stash
from pigit.termui import EVT_GOTO, keys
from pigit.termui.root import ComponentRoot
from pigit.termui.surface import Surface
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
    root.mount()
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
    assert by_key["5"].lower().find("graph") >= 0


def test_tab_cycles_status_stash_branch_commit_graph(runtime):
    app, root = _mount(runtime)
    assert _leaf(root) is app._status_panel

    root._handle_event(keys.KEY_TAB)
    assert _leaf(root) is app._stash_panel

    root._handle_event(keys.KEY_TAB)
    assert _leaf(root) is app._branch_panel

    root._handle_event(keys.KEY_TAB)
    assert _leaf(root) is app._commit_panel

    root._handle_event(keys.KEY_TAB)
    assert _leaf(root) is app._graph_panel

    root._handle_event(keys.KEY_TAB)
    assert _leaf(root) is app._status_panel


def test_shift_tab_cycles_backward(runtime):
    app, root = _mount(runtime)
    root._handle_event(keys.KEY_SHIFT_TAB)
    assert _leaf(root) is app._graph_panel
    root._handle_event(keys.KEY_SHIFT_TAB)
    assert _leaf(root) is app._commit_panel
    root._handle_event(keys.KEY_SHIFT_TAB)
    assert _leaf(root) is app._branch_panel


def test_tab_on_diff_closes_detail_and_cycles(runtime):
    """Tab while Diff detail is open closes detail then advances the product ring."""
    app, root = _mount(runtime)
    app._diff_panel.update(
        EVT_GOTO,
        target="diff",
        source=app._status_panel,
        content=["+a"],
    )
    app._body_view.show(app._diff_panel)
    assert app._is_detail_open()
    assert _leaf(root) is app._diff_panel

    root._handle_event(keys.KEY_TAB)
    assert not app._is_detail_open()
    assert _leaf(root) is app._stash_panel


def test_number_keys_land_on_each_panel(runtime):
    app, root = _mount(runtime)
    root._handle_event("2")
    assert _leaf(root) is app._stash_panel
    root._handle_event("3")
    assert _leaf(root) is app._branch_panel
    root._handle_event("4")
    assert _leaf(root) is app._commit_panel
    root._handle_event("5")
    assert _leaf(root) is app._graph_panel
    root._handle_event("1")
    assert _leaf(root) is app._status_panel


def test_each_number_key_moves_the_page_not_only_the_focus(runtime):
    """The focus leaf was already right before Stash had its own page: the
    Column handed focus to the stash panel without the product tab ever moving.
    The page is what has to change, so assert on the TabView as well."""
    app, root = _mount(runtime)
    for key, panel in (
        ("2", app._stash_panel),
        ("3", app._branch_panel),
        ("4", app._commit_panel),
        ("5", app._graph_panel),
        ("1", app._status_panel),
    ):
        root._handle_event(key)
        assert app._tab_view.visible is panel, f"key {key} did not switch the page"
        assert _leaf(root) is panel


def test_the_product_tabs_are_the_panel_ring(runtime):
    """`panel_ring` and the TabView children are the same five things, in the
    same order. That identity is the point of Stash having its own page, and
    the tab bar depends on it."""
    app, _root = _mount(runtime)
    children = [c.id for c in app._tab_view.children]
    assert children == ["status", "stash", "branch", "commit", "graph"]
    assert children == [p.id for p in app._panel_nav.panel_ring()]


def test_the_status_id_resolves_after_the_column_is_gone(runtime):
    """`route_to("status")` is how the app returns to Status after a repo
    switch, a merge conflict and a rebase. That id belonged to the Column that
    held Status+Stash, so it has to resolve to the panel now."""
    app, root = _mount(runtime)
    root._handle_event("2")
    assert app._tab_view.visible is app._stash_panel
    app._tab_view.route_to("status")
    assert app._tab_view.visible is app._status_panel


def test_the_stash_page_paints_its_rows(runtime):
    """Routing there mounts it and then loads it; the page has to carry rows,
    not come up empty."""
    app, root = _mount(runtime)
    app._stash_panel._vm.load_stashes = lambda: [
        Stash(ref="stash@{0}", sha="abc", msg="WIP on main")
    ]
    root._handle_event("2")
    root.resize((80, 24))
    surface = Surface(80, 24)
    root.paint(surface)
    assert "WIP on main" in "\n".join(surface.lines())


def test_routing_to_stash_loads_it_once(runtime):
    """`route_to` mounts the page and then calls its ``refresh``. Adding a
    load to ``mount`` on top of that would run ``git stash list`` twice for
    every visit."""
    app, root = _mount(runtime)
    calls: list[int] = []

    def _load() -> list[Stash]:
        calls.append(1)
        return []

    app._stash_panel._vm.load_stashes = _load
    root._handle_event("2")
    assert len(calls) == 1
    root._handle_event("1")
    root._handle_event("2")
    assert len(calls) == 2


def test_filter_consumes_digit_before_panel_goto(runtime):
    """An active search filter gets digits before the app-level goto bindings."""
    app, root = _mount(runtime)
    app._status_panel.search()  # activate the filter
    assert app._status_panel.search_active

    root._handle_event("4")
    assert app._status_panel.search_query == "4"
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
    assert not app._status_panel.search_active

    root._handle_event("4")
    assert _leaf(root) is app._commit_panel


def _body_ids(app: PigitApplication) -> list[str | None]:
    return [child.id for child in app._split_pane.children]


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
    app._tab_view.route_to("stash")
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
    assert "Enter" in toasts[0]  # the route that still works


def test_narrow_preview_toast_names_the_log_route_on_branches(
    runtime, monkeypatch
) -> None:
    """Branches have no Enter-to-diff path, so the hint differs by panel."""
    monkeypatch.setattr("pigit.app.terminal_size", lambda: (80, 24))
    toasts: list[str] = []
    monkeypatch.setattr(
        "pigit.app.show_toast", lambda msg, **_kwargs: toasts.append(msg)
    )
    app, root = _mount(runtime)
    app._tab_view.route_to("branch")

    root._handle_event("ctrl p")

    assert toasts
    assert "Graph" in toasts[0]
    assert "Enter" not in toasts[0]


def test_toggling_on_a_tab_without_a_preview_is_silent(runtime, monkeypatch) -> None:
    """Commit has no side preview at any width, so a narrow terminal is not
    the reason nothing happens there."""
    monkeypatch.setattr("pigit.app.terminal_size", lambda: (80, 24))
    toasts: list[str] = []
    monkeypatch.setattr(
        "pigit.app.show_toast", lambda msg, **_kwargs: toasts.append(msg)
    )
    app, _root = _mount(runtime)
    app._tab_view.route_to("commit")

    app.toggle_side_preview()

    assert toasts == []


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
    assert "Ctrl+r" not in commit  # the graph moved to its own tab


class TestWhileARewriteRuns:
    """Arriving at a panel mounts it, and Status reads the worktree the moment
    it appears -- the half-applied state the observe defer already refuses to
    poll for. So the user's own move is refused while a rewrite holds the gate."""

    def test_the_number_keys_do_not_move(self, runtime):
        app, root = _mount(runtime)
        root._handle_event("3")
        assert _leaf(root) is app._branch_panel

        app._session.worktree_gate.acquire()
        root._handle_event("1")
        root._handle_event("4")

        assert _leaf(root) is app._branch_panel

    def test_tab_does_not_cycle(self, runtime):
        app, root = _mount(runtime)
        app._session.worktree_gate.acquire()

        root._handle_event(keys.KEY_TAB)

        assert _leaf(root) is app._status_panel

    def test_navigation_resumes_when_the_rewrite_ends(self, runtime):
        app, root = _mount(runtime)
        root._handle_event("3")
        app._session.worktree_gate.acquire()
        root._handle_event("4")
        assert _leaf(root) is app._branch_panel

        app._session.worktree_gate.release()
        root._handle_event("4")

        assert _leaf(root) is app._commit_panel

    def test_the_mouse_picker_takes_the_same_route(self, runtime):
        app, root = _mount(runtime)
        root._handle_event("3")
        app._session.worktree_gate.acquire()

        app._on_panel_picker_select(app._commit_panel)

        assert _leaf(root) is app._branch_panel

    def test_the_apps_own_navigation_is_not_guarded(self, runtime):
        """The conflict handoff is the app moving the screen, not the user
        moving themselves -- it has to keep working while the flow still holds
        the gate, so it does not go through the navigator."""
        app, _root = _mount(runtime)
        app._session.worktree_gate.acquire()

        app.navigate_product("commit")

        assert app._tab_view.visible is app._commit_panel
