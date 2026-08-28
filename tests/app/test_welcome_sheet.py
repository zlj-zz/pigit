"""
Module: tests/app/test_welcome_sheet.py
Description: Welcome Sheet first-run, state, footer, and Help manual entry.
Author: Zev
Date: 2026-08-28
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from pigit.app import PigitApplication
from pigit.app_welcome import (
    WelcomeSheet,
    build_welcome_content,
    get_welcome_groups,
    should_auto_show_welcome,
    WELCOME_SHEET_MAX_FRACTION,
)
from pigit.termui.widgets.text_browser import block_inset, block_inset_for
from pigit.config_data import AppConfig
from pigit.termui import by_id
from pigit.termui.root import ComponentRoot
from pigit.termui.surface import Surface
from pigit.termui.types import LayerKind
from pigit.termui._runtime_context import RuntimeContext, _runtime_ctx
from pigit.welcome_state import load_welcome_seen, save_welcome_seen


@pytest.fixture
def runtime():
    ctx = RuntimeContext()
    token = _runtime_ctx.set(ctx)
    yield ctx
    _runtime_ctx.reset(token)


@pytest.fixture
def state_path(tmp_path, monkeypatch):
    path = tmp_path / "state.toml"
    monkeypatch.setattr("pigit.welcome_state.STATE_FILE_PATH", str(path))
    return path


def _mount(
    runtime: RuntimeContext, *, config: AppConfig | None = None
) -> tuple[PigitApplication, ComponentRoot]:
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
    app.setup_root(root)
    root.mount()
    root.resize((100, 50))
    app._help_popup.resize((100, 50))
    return app, root


@pytest.fixture
def mount_welcome_app(runtime):
    """Mount app with terminal size large enough for auto-show Welcome."""
    with patch("pigit.app_welcome.terminal_size", return_value=(100, 50)):
        yield _mount(runtime)


def test_build_welcome_content_matches_help_shape(mount_welcome_app):
    app, _root = mount_welcome_app
    text = " ".join(seg.text for row in build_welcome_content(app) for seg in row)
    assert "[Panels]" in text
    assert "[Global]" in text
    assert "Stay in the terminal. Ship the commit." in text
    assert "hunk-level staging" in text
    assert "pigit repo" in text
    assert "pigit cmd" in text
    assert "interactive help panel" in text
    assert "github.com/zlj-zz/pigit" in text
    assert "Status" in text
    assert "Stash" in text
    assert "P i g i t" in text
    assert "●" in text
    assert "Full help" in text


def test_welcome_panel_keys_match_app_bindings(mount_welcome_app):
    app, _root = mount_welcome_app
    groups = get_welcome_groups(app)
    panels = next(entries for title, entries in groups if title == "Panels")
    by_action = {row.action: row for row in panels}
    app_rows = {r.action: r for r in app.get_executable_bindings()}
    for action in (
        "universal.goto_status",
        "universal.goto_stash",
        "universal.goto_branch",
        "universal.goto_commit",
    ):
        assert panels[0].keys_display  # non-empty
        assert by_action[action].keys_display == app_rows[action].keys_display


def test_content_block_inset_centers_copy(mount_welcome_app):
    app, _root = mount_welcome_app
    rows = build_welcome_content(app)
    inset = block_inset(100, rows, align="center", min_inset=4)
    assert inset >= 4
    sheet = WelcomeSheet(on_dismiss=lambda: None, rows=rows)
    sheet.resize((100, 24))
    surface = Surface(100, 24)
    sheet.paint(surface)
    lines = surface.lines()
    status = next(line for line in lines if "Status" in line and "stage" in line)
    assert status[:inset].strip() == ""
    assert "1" in status


def test_welcome_preferred_height_uses_two_thirds_cap(mount_welcome_app):
    app, _root = mount_welcome_app
    rows = build_welcome_content(app)
    sheet = WelcomeSheet(on_dismiss=lambda: None, rows=rows)
    term_h = 30
    want = len(rows) + 1
    cap = int(term_h * WELCOME_SHEET_MAX_FRACTION)
    assert sheet.preferred_sheet_height(term_h) == min(want, cap)
    tall = WelcomeSheet(on_dismiss=lambda: None, rows=rows)
    assert tall.preferred_sheet_height(60) == want
    from pigit.termui.widgets.sheet import Sheet

    assert Sheet.resolve_height(
        tall,
        30,
        max_fraction=WELCOME_SHEET_MAX_FRACTION,
    ) == min(want, cap)


def test_save_and_load_welcome_seen(state_path):
    assert load_welcome_seen() is False
    save_welcome_seen()
    assert load_welcome_seen() is True
    assert state_path.read_text() == "welcome_seen = true\n"


def test_load_welcome_seen_tolerates_corrupt_toml(state_path):
    state_path.write_text("welcome_seen = not-valid\n", encoding="utf-8")
    assert load_welcome_seen() is False


def test_save_welcome_seen_preserves_other_keys(state_path):
    state_path.write_text("other_flag = true\n", encoding="utf-8")
    save_welcome_seen()
    text = state_path.read_text()
    assert "other_flag = true" in text
    assert "welcome_seen = true" in text


def test_should_auto_show_respects_seen(state_path):
    config = AppConfig(show_welcome=True)
    assert (
        should_auto_show_welcome(config, None, min_terminal_rows=10, content_rows=20)
        is False
    )
    save_welcome_seen()
    assert (
        should_auto_show_welcome(
            config, object(), min_terminal_rows=10, content_rows=20
        )
        is False
    )


def test_after_start_shows_welcome_when_unseen(mount_welcome_app, state_path):
    app, root = mount_welcome_app
    with patch("pigit.app.show_toast") as toast:
        app.after_start()
    top = root._layer_stack.top(LayerKind.SHEET)
    assert top is not None
    assert isinstance(top._child, WelcomeSheet)
    toast.assert_not_called()


def test_after_start_no_welcome_when_seen(mount_welcome_app, state_path):
    save_welcome_seen()
    app, root = mount_welcome_app
    with patch("pigit.app.show_toast") as toast:
        app.after_start()
    assert root._layer_stack.top(LayerKind.SHEET) is None
    calls = [str(c) for c in toast.call_args_list]
    assert not any("Welcome to Pigit" in c for c in calls)


def test_close_welcome_marks_seen(mount_welcome_app, state_path):
    app, root = mount_welcome_app
    app.after_start()
    top = root._layer_stack.top(LayerKind.SHEET)
    assert top is not None
    top._child.close()
    assert load_welcome_seen() is True
    assert root._layer_stack.top(LayerKind.SHEET) is None


def test_show_welcome_manual_does_not_mark_seen(mount_welcome_app, state_path):
    assert load_welcome_seen() is False
    app, _root = mount_welcome_app
    app.show_welcome()
    sheet = app._root._layer_stack.top(LayerKind.SHEET)
    assert sheet is not None
    sheet._child.close()
    assert load_welcome_seen() is False


def test_footer_shows_welcome_keys_when_sheet_open(mount_welcome_app, state_path):
    app, _root = mount_welcome_app
    app.after_start()
    footer = by_id("footer")
    surface = Surface(100, 2)
    footer.resize((100, 2))
    footer.paint(surface)
    content = surface.lines()[1]
    assert "Close" in content
    assert "Navigate" not in content
    assert "Quit" not in content


def test_show_welcome_noop_when_overlay_open(mount_welcome_app, state_path):
    app, _root = mount_welcome_app
    app.toggle_help()
    app.show_welcome()
    assert app._help_popup.open is True
