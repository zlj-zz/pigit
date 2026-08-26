"""
Module: tests/app/test_inspector_sheet.py
Description: Tests for InspectorSheet formatting, height, and open/close.
Author: Zev
Date: 2026-08-19
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from pigit.app import PigitApplication
from pigit.app_inspector import InspectorSheet
from pigit.config_data import AppConfig
from pigit.termui._layer import LayerKind
from pigit.termui.root import ComponentRoot
from pigit.termui._runtime_context import RuntimeContext, _runtime_ctx
from pigit.app_theme import THEME
from pigit.app_types import (
    BranchSnapshot,
    CommitSnapshot,
    FileSnapshot,
    StashSnapshot,
)
from pigit.termui import palette
from pigit.termui.segment import Segment


def _plain(rows: list[list[Segment]]) -> list[str]:
    return ["".join(seg.text for seg in row) for row in rows]


def test_format_file_omits_xy_prose():
    rows = InspectorSheet.format(
        FileSnapshot(
            identity="a.py",
            path="old.py → a.py",
            blobs="index ≠ worktree",
            stages="1, 2, 3",
            size="1.2K",
            mode="644",
            last="deadbee Fix layout  (zev, 2 days ago)",
        )
    )
    lines = _plain(rows)
    text = "\n".join(lines)
    assert lines[0] == "Inspector · file · a.py"
    assert "old.py → a.py" in text
    assert "staged" not in text
    assert "unstaged" not in text
    assert rows[0][0].fg == THEME.fg_panel_title
    assert rows[0][0].style_flags & palette.STYLE_BOLD
    assert rows[0][2].fg == THEME.fg_info
    last_row = rows[-1]
    assert last_row[1].text == "deadbee"
    assert last_row[1].fg == THEME.fg_muted


def test_format_branch_includes_tracking_and_recent():
    rows = InspectorSheet.format(
        BranchSnapshot(
            identity="feat",
            tip="abc1234deadbeef",
            created="2026-01-01",
            contained=True,
            current="no",
            upstream="origin/feat",
            ahead="2",
            behind="1",
            recent_msg="Add thing",
            recent_author="Zev",
        )
    )
    lines = _plain(rows)
    text = "\n".join(lines)
    assert lines[0] == "Inspector · branch · feat"
    assert "abc1234deadbeef" in text
    assert "origin/feat" in text
    assert "Add thing" in text
    assert "Zev" in text
    assert "contained yes" in text
    tip_row = rows[1]
    assert tip_row[1].fg == THEME.fg_muted
    by_label = next(r for r in rows if r[0].text.startswith("ahead"))
    assert by_label[1].fg == THEME.fg_success
    behind_row = next(r for r in rows if r[0].text.startswith("behind"))
    assert behind_row[1].fg == THEME.fg_warning
    contained_row = rows[-1]
    assert contained_row[1].fg == THEME.fg_success


def test_format_branch_hides_unknown_recent_and_tracking():
    rows = InspectorSheet.format(
        BranchSnapshot(
            identity="feat",
            tip="abc1234deadbeef",
            created=None,
            contained=None,
            current="no",
            upstream="none",
            ahead="0",
            behind="0",
            recent_msg="?",
            recent_author="?",
        )
    )
    lines = _plain(rows)
    text = "\n".join(lines)
    assert "contained ?" in text
    assert "none" in text
    assert "Add thing" not in text


def test_format_commit_includes_metadata():
    rows = InspectorSheet.format(
        CommitSnapshot(
            identity="abc1234",
            sha="abc1234deadbeef",
            msg="Fix layout",
            author="Zev",
            when="2 days ago",
            status="unpushed",
            tags="v1.0",
            parents=["parent1"],
            files=[("a.py", 10, 5)],
            total_add=10,
            total_del=5,
        )
    )
    lines = _plain(rows)
    text = "\n".join(lines)
    assert lines[0] == "Inspector · commit · abc1234"
    assert "Fix layout" in text
    assert "Zev" in text
    assert "2 days ago" in text
    assert "unpushed" in text
    assert "v1.0" in text
    assert "a.py" in text
    assert "+10" in text
    changes = rows[8]
    assert changes[1].fg == THEME.fg_success
    assert changes[3].fg == THEME.fg_danger
    file_row = rows[9]
    assert file_row[3].text == "+10"
    assert file_row[3].fg == THEME.fg_success
    assert file_row[5].fg == THEME.fg_danger
    status_row = rows[4]
    assert status_row[1].text == "unpushed"
    assert status_row[1].fg == THEME.fg_unpushed_commit


def test_format_stash_includes_numstat():
    rows = InspectorSheet.format(
        StashSnapshot(
            identity="stash@{0}",
            author="Zev",
            when="2 days ago",
            parents=["abc"],
            files=[("a.py", 1, 0)],
            total_add=1,
            total_del=0,
        )
    )
    lines = _plain(rows)
    text = "\n".join(lines)
    assert lines[0] == "Inspector · stash · stash@{0}"
    assert "a.py" in text


def test_inspector_sheet_browser_has_no_bg():
    sheet = InspectorSheet([[Segment("hello")]])
    assert sheet._browser._bg is None


def test_sheet_height_clamps():
    assert InspectorSheet.sheet_height(["a", "b"], 24, border=1) == 3
    tall = [str(i) for i in range(40)]
    assert InspectorSheet.sheet_height(tall, 24, border=1) == 12


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
    root.mount()
    root.resize((80, 24))
    return app, root


def _tall_commit() -> CommitSnapshot:
    files = [(f"f{i}.py", 1, 0) for i in range(40)]
    return CommitSnapshot(
        identity="abc1234",
        sha="abc1234deadbeef",
        msg="Fix layout",
        author="Zev",
        when="2 days ago",
        status="unpushed",
        tags="none",
        parents=["parent"],
        files=files,
        total_add=40,
        total_del=0,
    )


def test_open_inspector_is_top_sheet_not_body_child(runtime):
    app, root = _mount(runtime)
    with (
        patch.object(
            app._status_panel, "get_inspector_snapshot", return_value=_tall_commit()
        ),
        patch("pigit.app.run_async", side_effect=lambda work, cb: cb(work())),
    ):
        app.open_inspector()
    ids = [child.id for child in app._split_pane.children]
    assert "inspector" not in ids
    sheet = root._layer_stack.top(LayerKind.SHEET)
    assert sheet is not None
    assert sheet._edge == "top"
    assert sheet._bg is None
    assert isinstance(sheet._child, InspectorSheet)


def test_j_scrolls_sheet_not_status_list(runtime):
    app, root = _mount(runtime)
    before = app._status_panel.curr_no
    with (
        patch.object(
            app._status_panel, "get_inspector_snapshot", return_value=_tall_commit()
        ),
        patch("pigit.app.run_async", side_effect=lambda work, cb: cb(work())),
    ):
        app.open_inspector()
    sheet = root._layer_stack.top(LayerKind.SHEET)
    assert sheet is not None
    browser = sheet._child._browser
    assert browser.scroll_i == 0
    root._layer_stack.dispatch("j")
    assert app._status_panel.curr_no == before
    assert browser.scroll_i == 1


def test_esc_and_i_dismiss_inspector(runtime):
    app, root = _mount(runtime)
    with (
        patch.object(
            app._status_panel, "get_inspector_snapshot", return_value=_tall_commit()
        ),
        patch("pigit.app.run_async", side_effect=lambda work, cb: cb(work())),
    ):
        app.open_inspector()
    assert root._layer_stack.top(LayerKind.SHEET) is not None
    root._layer_stack.dispatch("esc")
    assert root._layer_stack.top(LayerKind.SHEET) is None

    with (
        patch.object(
            app._status_panel, "get_inspector_snapshot", return_value=_tall_commit()
        ),
        patch("pigit.app.run_async", side_effect=lambda work, cb: cb(work())),
    ):
        app.open_inspector()
    root._layer_stack.dispatch("I")
    assert root._layer_stack.top(LayerKind.SHEET) is None


def test_open_inspector_shows_placeholder_while_loading(runtime):
    app, root = _mount(runtime)
    with patch("pigit.app.run_async", return_value=MagicMock()) as ra:
        app.open_inspector()
    sheet = root._layer_stack.top(LayerKind.SHEET)
    assert sheet is not None
    assert isinstance(sheet._child, InspectorSheet)
    text = "".join(s.text for row in sheet._child._browser._rows for s in row)
    assert "Inspecting" in text
    ra.assert_called_once()


def test_inspector_load_dropped_when_placeholder_closed(runtime):
    app, root = _mount(runtime)
    captured: dict[str, object] = {}

    def fake_run_async(work, cb):
        captured["cb"] = cb
        return MagicMock()

    with patch("pigit.app.run_async", side_effect=fake_run_async):
        app.open_inspector()
    root._layer_stack.dispatch("esc")  # close the placeholder
    captured["cb"](_tall_commit())  # a late result must not re-open the sheet
    assert root._layer_stack.top(LayerKind.SHEET) is None


def test_diff_view_toasts_no_inspector(runtime):
    app, root = _mount(runtime)
    app._body_view.show(app._diff_panel)
    with patch("pigit.app.show_toast") as toast:
        app.open_inspector()
    toast.assert_called_once()
    assert toast.call_args[0][0] == "No inspector for this view"
    assert root._layer_stack.top(LayerKind.SHEET) is None
