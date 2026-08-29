# -*- coding: utf-8 -*-
"""
Module: tests/app/test_diff_file_nav.py
Description: DiffViewer file sections, ``,``/``.`` jump, top bar, FilePicker.
Author: Zev
Date: 2026-08-29
"""

from __future__ import annotations

from pigit.app import PigitApplication
from pigit.app_diff import DiffType, DiffViewer
from pigit.app_anchored_picker import FilePicker
from pigit.config_data import AppConfig
from pigit.termui import Component
from pigit.termui._runtime_context import RuntimeContext, _runtime_ctx, set_overlay_host
from pigit.termui.mouse import MouseButton, MouseEvent, MouseKind
from pigit.termui.root import ComponentRoot
from pigit.termui.surface import Surface

import pytest


def _multi_file_diff() -> list[str]:
    return [
        "diff --git a/a.py b/a.py",
        "--- a/a.py",
        "+++ b/a.py",
        "@@ -1,1 +1,1 @@",
        "-old_a",
        "+new_a",
        "diff --git a/b.py b/b.py",
        "--- a/b.py",
        "+++ b/b.py",
        "@@ -1,1 +1,1 @@",
        "-old_b",
        "+new_b",
        "diff --git a/bin.dat b/bin.dat",
        "Binary files a/bin.dat and b/bin.dat differ",
    ]


def _viewer_with_commit(lines: list[str]) -> DiffViewer:
    dv = DiffViewer()
    dv.set_diff_type(DiffType.COMMIT)
    dv.set_content(lines)
    return dv


def test_file_sections_multi_including_binary():
    dv = _viewer_with_commit(_multi_file_diff())
    assert [s.path for s in dv._file_sections] == ["a.py", "b.py", "bin.dat"]
    assert dv._file_sections[0].header_start == 0
    assert dv._file_sections[0].first_hunk_start == 3
    assert dv._file_sections[1].header_start == 6
    assert dv._file_sections[1].first_hunk_start == 9
    assert dv._file_sections[2].header_start == 12
    assert dv._file_sections[2].first_hunk_start == 12


def test_file_sections_quoted_path():
    lines = [
        'diff --git "a/my file" "b/my file"',
        '--- "a/my file"',
        '+++ "b/my file"',
        "@@ -1,1 +1,1 @@",
        "-x",
        "+y",
    ]
    dv = _viewer_with_commit(lines)
    assert len(dv._file_sections) == 1
    assert dv._file_sections[0].path == "my file"


def test_file_sections_single_and_plain():
    single = _viewer_with_commit(
        [
            "diff --git a/only.py b/only.py",
            "@@ -1,1 +1,1 @@",
            "-a",
            "+b",
        ]
    )
    assert len(single._file_sections) == 1
    plain = DiffViewer()
    plain.set_content(["line1", "line2"])
    assert plain._file_sections == []


def test_current_file_index_header_belongs_to_following_section():
    dv = _viewer_with_commit(_multi_file_diff())
    dv._line_i = 6  # header of b.py
    assert dv.current_file_index() == 1
    dv._line_i = 5  # last line of a.py hunk
    assert dv.current_file_index() == 0


def test_current_file_index_subject_block_maps_to_first_section():
    """``git show`` subject lines before the first ``diff --git`` map to section 0."""
    show = ["commit 3f2a1c9", "Author: zev", "    fix", ""]
    dv = _viewer_with_commit(show + _multi_file_diff())
    dv._line_i = 0
    assert dv.current_file_index() == 0


def test_next_prev_file_jump_and_bounds():
    dv = _viewer_with_commit(_multi_file_diff())
    dv._line_i = 4
    dv.next_file()
    assert dv._line_i == 9
    dv.next_file()
    assert dv._line_i == 12
    dv.next_file()
    assert dv._line_i == 12
    dv.prev_file()
    assert dv._line_i == 9
    dv._line_i = 0
    dv.prev_file()
    assert dv._line_i == 0


def test_single_file_nav_noop():
    dv = _viewer_with_commit(
        ["diff --git a/only.py b/only.py", "@@ -1 +1 @@", "-a", "+b"]
    )
    dv._line_i = 2
    dv.next_file()
    dv.prev_file()
    assert dv._line_i == 2


def test_hunk_mode_disables_file_nav():
    lines = [
        "diff --git a/a.py b/a.py",
        "@@ -1 +1 @@",
        "-a",
        "+b",
        "diff --git a/b.py b/b.py",
        "@@ -1 +1 @@",
        "-c",
        "+d",
    ]
    dv = DiffViewer()
    dv.set_diff_type(DiffType.UNSTAGED)
    dv.set_content(lines)
    dv._hunk_mode = True
    dv._line_i = 2
    dv.next_file()
    assert dv._line_i == 2
    surface = Surface(80, 20)
    dv.resize((80, 20))
    dv.paint(surface)
    text = "".join(c.char for c in surface._rows[0])
    assert "▸" not in text


def test_top_bar_renders_and_bottom_badge_gone():
    dv = _viewer_with_commit(_multi_file_diff())
    dv._line_i = 9
    dv.resize((80, 20))
    surface = Surface(80, 20)
    dv.paint(surface)
    top = "".join(c.char for c in surface._rows[0]).rstrip()
    assert "▸ 2/3" in top
    assert "b.py" in top
    bottom = "".join(c.char for c in surface._rows[19])
    assert " b.py " not in bottom


def test_top_bar_shows_before_first_diff_git():
    """A ``git show`` commit subject block precedes the first ``diff --git``."""
    show = [
        "commit 3f2a1c9",
        "Author: zev",
        "Date:  Fri Aug 28 2026",
        "",
        "    fix",
        "",
    ]
    dv = _viewer_with_commit(show + _multi_file_diff())
    dv._line_i = 0  # cursor still in the subject block
    dv.resize((80, 20))
    surface = Surface(80, 20)
    dv.paint(surface)
    top = "".join(c.char for c in surface._rows[0]).rstrip()
    assert "▸ 1/3" in top
    assert "a.py" in top


def test_top_bar_borderless_skipped():
    dv = _viewer_with_commit(_multi_file_diff())
    # can_draw_box requires w > LINE_NO_WIDTH + 3 (== 7).
    dv.resize((6, 5))
    surface = Surface(6, 5)
    dv.paint(surface)
    top = "".join(c.char for c in surface._rows[0])
    assert "▸" not in top
    assert dv._file_nav_counter_cols is None


def test_global_origin_sums_parent_chain():
    parent = Component(x=3, y=5, size=(40, 20))
    child = DiffViewer(x=4, y=6, size=(30, 15))
    child.parent = parent
    assert child.global_origin() == (5, 9)


def test_mouse_counter_opens_picker_callback():
    picked: list[tuple[int, int]] = []
    dv = DiffViewer(on_file_picker=lambda r, c: picked.append((r, c)))
    dv.set_diff_type(DiffType.COMMIT)
    dv.set_content(_multi_file_diff())
    dv.resize((80, 20))
    dv.x, dv.y = 2, 3
    surface = Surface(80, 20)
    dv.paint(surface)
    assert dv._file_nav_counter_cols is not None
    start, end = dv._file_nav_counter_cols
    event = MouseEvent(
        kind=MouseKind.PRESS,
        button=MouseButton.LEFT,
        row=1,
        col=start + 1,
    )
    assert dv.handle_mouse(event) is True
    assert picked == [(1, 2 + start)]

    picked.clear()
    miss = MouseEvent(
        kind=MouseKind.PRESS,
        button=MouseButton.LEFT,
        row=1,
        col=end + 3,
    )
    assert dv.handle_mouse(miss) is False
    assert picked == []


def test_picker_wheel_moves_cursor():
    picker = FilePicker(entries=["a.py", "b.py", "c.py"], current_index=0)
    picker._cursor = 0
    down = MouseEvent(kind=MouseKind.PRESS, button=MouseButton.WHEEL_DOWN, row=1, col=1)
    assert picker.handle_mouse(down) is True
    assert picker._cursor == 1
    up = MouseEvent(kind=MouseKind.PRESS, button=MouseButton.WHEEL_UP, row=1, col=1)
    assert picker.handle_mouse(up) is True
    assert picker._cursor == 0
    assert picker.handle_mouse(up) is True  # clamps at the first row
    assert picker._cursor == 0


def test_file_picker_lists_and_selects():
    selected: list[int] = []
    picker = FilePicker(
        entries=["a.py", "b.py", "bin.dat"],
        current_index=1,
        on_select=lambda i: selected.append(i),
    )
    assert picker.is_current_at(1)
    picker._cursor = 2
    picker.activate_selected()
    assert selected == [2]


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


def test_open_diff_file_picker_jumps(runtime):
    app, _root = _mount(runtime)
    dv = app._diff_panel
    dv.set_diff_type(DiffType.COMMIT)
    dv.set_content(_multi_file_diff())
    dv._line_i = 0
    app.open_diff_file_picker(5, 10)
    popup = app._panel_picker_popup
    assert popup is not None
    assert popup.open is True
    picker = popup._child
    assert isinstance(picker, FilePicker)
    assert picker._entries == ["a.py", "b.py", "bin.dat"]
    picker._cursor = 1
    picker.activate_selected()
    assert dv._line_i == 9
