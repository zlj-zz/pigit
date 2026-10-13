# -*- coding: utf-8 -*-
"""
Module: tests/app/test_commit_editor.py
Description: CommitEditor status bar shortcuts, reached by key and by mouse.
Author: Zev
Date: 2026-08-21
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from pigit.app_commit_editor import CommitEditor
from pigit.app_theme import THEME
from pigit.termui import Component, ComponentRoot, keys
from pigit.termui._runtime_context import (
    RuntimeContext,
    _runtime_ctx,
    reset_focus_manager,
    reset_overlay_host,
    set_focus_manager,
    set_overlay_host,
)
from pigit.termui.mouse import MouseButton, MouseEvent, MouseKind
from pigit.termui.surface import Surface
from pigit.termui.theme import get_theme, set_theme
from pigit.termui.widgets import (
    Label,
    ShortcutHints,
    StaticList,
    measure_shortcut_hints,
)


class _Body(Component):
    """The root needs something to paint under the sheet."""

    def paint(self, surface) -> None:
        pass


def _editor(**overrides) -> CommitEditor:
    kwargs = dict(
        vm=MagicMock(),
        staged_files=[],
        on_submit=lambda _msg: None,
        on_cancel=lambda: None,
    )
    kwargs.update(overrides)
    return CommitEditor(**kwargs)


def _status_bar_text(editor: CommitEditor) -> str:
    """The status bar as painted, so a column can be found by its own glyphs."""
    return " " + "  ".join(f"{label} {desc}" for label, desc, _a in editor._shortcuts)


@pytest.fixture(autouse=True)
def _theme():
    previous = get_theme()
    set_theme(THEME)
    yield
    set_theme(previous)


@pytest.fixture
def root():
    """A real ComponentRoot, so a click travels the production mouse path."""
    runtime = RuntimeContext()
    token = _runtime_ctx.set(runtime)
    node = ComponentRoot(_Body())
    node.resize((80, 24))
    set_overlay_host(node)
    set_focus_manager(node._focus_manager)
    yield node
    reset_overlay_host()
    reset_focus_manager()
    _runtime_ctx.reset(token)


def _click_everything_but_the_strip(root, sheet, editor) -> list[Component]:
    """Click every sheet cell that is not the hint strip.

    Returns:
        One component per distinct target those clicks landed on.
    """
    strip = editor._shortcut_hints
    targets: dict[str, Component] = {}
    width, height = sheet._size
    for col in range(sheet.y, sheet.y + width):
        for row in range(sheet.x, sheet.x + height):
            hit = sheet._hit_test(col, row)
            if hit is None or hit[0] is strip:
                continue
            targets.setdefault(type(hit[0]).__name__, hit[0])
            root._handle_mouse(
                MouseEvent(
                    col=col, row=row, button=MouseButton.LEFT, kind=MouseKind.PRESS
                )
            )
    return list(targets.values())


def _click_strip(root, sheet, editor, label: str) -> bool:
    """Click *label* on the hint strip through the root's own mouse routing.

    The strip's column comes from the text the status bar paints; where it sits
    on screen comes from the sheet's own hit-test, so nothing here re-derives
    the editor's geometry.
    """
    strip = editor._shortcut_hints
    wanted = _status_bar_text(editor).index(label)  # 0-based within the strip
    width, height = sheet._size
    for col in range(sheet.y, sheet.y + width):
        for row in range(sheet.x, sheet.x + height):
            hit = sheet._hit_test(col, row)
            if hit is None or hit[0] is not strip:
                continue
            return root._handle_mouse(
                MouseEvent(
                    col=col + (wanted - (hit[1] - 1)),
                    row=row,
                    button=MouseButton.LEFT,
                    kind=MouseKind.PRESS,
                )
            )
    raise AssertionError("the sheet never routes a click to the hint strip")


class TestTheStatusBar:
    def test_shortcut_hints_width_matches_pairs(self) -> None:
        hints = _editor()._shortcut_hints
        assert hints.preferred_width == measure_shortcut_hints(
            [("Tab", "body"), ("Ctrl+Enter", "commit"), ("Esc", "cancel")]
        )
        assert hints.preferred_width > 20

    def test_commit_editor_status_bar_is_lint_plus_shortcuts(self) -> None:
        editor = _editor()
        assert editor._status_bar.children == [editor._lint_bar, editor._shortcut_hints]
        assert editor._editor_col.children[-1] is editor._status_bar

    def test_shortcut_hints_render_keys(self) -> None:
        hints = ShortcutHints([("Tab", "body")])
        hints.resize((hints.preferred_width, 1))
        surface = Surface(hints.preferred_width, 1)
        hints.paint(surface)
        cell = surface.rows()[0][1]
        assert cell.char == "T"
        assert cell.fg == get_theme().fg_primary

    def test_commit_editor_uses_label_and_static_list(self) -> None:
        editor = _editor()
        assert isinstance(editor._staged_header, Label)
        assert isinstance(editor._staged_list, StaticList)


class TestTheKeyboardPath:
    """Unchanged: the strip is an extra door to the same three actions."""

    def test_ctrl_enter_still_submits(self) -> None:
        submitted: list[str] = []
        editor = _editor(on_submit=submitted.append)
        editor._subject.set_value("fix: a thing")

        editor.dispatch_overlay_key(keys.KEY_CTRL_ENTER)

        assert submitted == ["fix: a thing"]

    def test_tab_still_moves_to_the_body(self) -> None:
        editor = _editor()
        editor.dispatch_overlay_key(keys.KEY_TAB)
        assert editor.focus_child is editor._body


class TestTheMousePath:
    def test_a_click_inside_the_editor_reaches_the_strip(self, root) -> None:
        """The editor paints through ``_root`` without registering it as a
        child, so hit-testing has to go through the same door -- otherwise
        nothing inside the editor is ever the click target."""
        editor = _editor()
        editor.resize((80, 12))
        width, height = editor._size

        reached = [
            editor._hit_test(col, row)
            for row in range(1, height + 1)
            for col in range(1, width + 1)
        ]

        assert any(
            hit is not None and hit[0] is editor._shortcut_hints for hit in reached
        ), "the hint strip is unreachable by hit-test"

    def test_clicking_ctrl_enter_commits(self, root) -> None:
        submitted: list[str] = []
        editor = _editor(on_submit=submitted.append)
        sheet = root.show_sheet(editor, height=12)
        editor._subject.set_value("fix: a thing")

        assert _click_strip(root, sheet, editor, "Ctrl+Enter") is True
        assert submitted == ["fix: a thing"]

    def test_clicking_esc_cancels(self, root) -> None:
        cancelled: list[bool] = []
        editor = _editor(on_cancel=lambda: cancelled.append(True))
        sheet = root.show_sheet(editor, height=12)

        _click_strip(root, sheet, editor, "Esc")

        assert cancelled == [True]

    def test_clicking_tab_focuses_the_body(self, root) -> None:
        editor = _editor()
        sheet = root.show_sheet(editor, height=12)

        _click_strip(root, sheet, editor, "Tab")

        assert editor.focus_child is editor._body

    def test_the_strip_is_the_editors_only_click_target(self, root) -> None:
        """Opening up hit-testing made every component in the editor reachable,
        and the rest of it is inert only because they inherit the base
        ``handle_mouse``. Should one of them ever grow a mouse behaviour --
        click-to-place-cursor on an input, say -- this fails and the new
        behaviour gets a decision instead of arriving in an unrelated diff."""
        submitted: list[str] = []
        cancelled: list[bool] = []
        editor = _editor(
            on_submit=submitted.append, on_cancel=lambda: cancelled.append(True)
        )
        sheet = root.show_sheet(editor, height=12)
        editor._subject.set_value("fix: a thing")

        clicked = _click_everything_but_the_strip(root, sheet, editor)
        names = {type(component).__name__ for component in clicked}
        overrides = [
            type(component).__name__
            for component in clicked
            if component.handle_mouse.__func__ is not Component.handle_mouse
        ]

        assert {"InputLine", "StaticList"} <= names, "nothing real was clicked"
        assert overrides == [], f"new mouse behaviour in the editor: {overrides}"
        assert submitted == [] and cancelled == []
        assert editor._focus_index == 0, "a click moved the focus"

    def test_a_click_elsewhere_in_the_sheet_does_nothing(self, root) -> None:
        """Only the strip is a target. The editor takes the click and ignores
        it, which is what keeps it from falling through to the panel below."""
        cancelled: list[bool] = []
        editor = _editor(on_cancel=lambda: cancelled.append(True))
        sheet = root.show_sheet(editor, height=12)

        consumed = root._handle_mouse(
            MouseEvent(
                col=sheet.y,
                row=sheet.x + 1,
                button=MouseButton.LEFT,
                kind=MouseKind.PRESS,
            )
        )

        assert consumed is True
        assert cancelled == []
