"""
Module: tests/termui/test_binding_browser.py
Description: Tests for ExecutableBinding derivation and BindingBrowser cursor/invoke.
Author: Zev
Date: 2026-08-27
"""

from __future__ import annotations

from dataclasses import replace
from unittest import mock

from pigit.termui import bind_action, keys
from pigit.termui.bindings import (
    collect_action_bindings,
    derive_executable_bindings,
    derive_help_entries,
)
from pigit.termui.component import Component
from pigit.termui.mouse import MouseButton, MouseEvent, MouseKind
from pigit.termui.viewport_hit import DOUBLE_CLICK_MS
from pigit.termui.widgets.binding_browser import BindingBrowser, _is_dismiss_only_action


class _Owner(Component):
    keymap_namespace = "demo"

    @bind_action("alpha", "a", desc="Do alpha")
    def do_alpha(self) -> None:
        self.hit = "alpha"

    @bind_action("beta", "b", desc="Do beta with a very long description that wraps")
    def do_beta(self) -> None:
        self.hit = "beta"

    @bind_action("help", "?", desc="Toggle help")
    def toggle_help(self) -> None:
        self.hit = "help"


def test_derive_executable_bindings_and_help_projection() -> None:
    owner = _Owner()
    rows = derive_executable_bindings(owner._action_bindings, owner)
    assert [r.action for r in rows] == ["demo.alpha", "demo.beta", "demo.help"]
    assert rows[0].keys_display == "a"
    assert callable(rows[0].invoke)
    projected = derive_help_entries(owner._action_bindings, owner)
    assert projected == [(r.keys_display, r.desc) for r in rows]


def test_derive_omits_missing_target() -> None:
    owner = _Owner()
    bindings = list(owner._action_bindings)
    broken = bindings[0]
    bindings[0] = replace(broken, target="missing_method")
    rows = derive_executable_bindings(bindings, owner)
    assert all(r.action != "demo.alpha" for r in rows)


def test_dismiss_only_help() -> None:
    assert _is_dismiss_only_action("universal.help")
    assert not _is_dismiss_only_action("panel.help")
    assert not _is_dismiss_only_action("demo.alpha")


def test_binding_browser_cursor_skips_headers_and_clamps() -> None:
    owner = _Owner()
    rows = owner.get_executable_bindings()
    browser = BindingBrowser(inner_width=40, inner_height=12)
    browser.resize((80, 24))
    browser.set_groups([("Panel", rows[:2]), ("Global", rows[2:])])
    assert browser.selected_binding() is rows[0]
    browser.move_up()
    assert browser._cursor == 0
    browser.move_down()
    assert browser.selected_binding() is rows[1]
    browser.move_down()
    assert browser.selected_binding() is rows[2]
    browser.move_down()
    assert browser._cursor == 2


def test_binding_browser_wrapped_desc_one_selectable() -> None:
    owner = _Owner()
    rows = owner.get_executable_bindings()
    browser = BindingBrowser(inner_width=24, inner_height=12)
    browser.resize((40, 24))
    browser.set_groups([("Panel", [rows[1]])])
    assert len(browser._selectable) == 1
    wrapped_lines = [sel for _s, sel in browser._render if sel == 0]
    assert len(wrapped_lines) >= 1


def test_activate_selected_dismiss_then_invoke() -> None:
    owner = _Owner()
    owner.hit = None
    rows = owner.get_executable_bindings()
    closed: list[bool] = []
    browser = BindingBrowser(
        inner_width=40,
        inner_height=12,
        on_toggle=lambda: closed.append(True),
    )
    browser.resize((80, 24))
    browser.set_groups([("Panel", [rows[0]])])
    browser.activate_selected()
    assert closed == [True]
    assert owner.hit == "alpha"


def test_activate_help_row_dismiss_only() -> None:
    owner = _Owner()
    owner.hit = None
    rows = owner.get_executable_bindings()
    help_row = next(r for r in rows if r.action.endswith(".help"))
    universal_help = replace(help_row, action="universal.help")
    closed: list[bool] = []
    browser = BindingBrowser(
        inner_width=40,
        on_toggle=lambda: closed.append(True),
    )
    browser.resize((80, 24))
    browser.set_groups([("Global", [universal_help])])
    browser.activate_selected()
    assert closed == [True]
    assert owner.hit is None


def test_collect_still_used_by_component() -> None:
    owner = _Owner()
    assert collect_action_bindings(_Owner, "demo")
    assert keys.KEY_ENTER in dict(BindingBrowser.BINDINGS)


# ---------------------------------------------------------------------------
# Left-click selection and double-click activation
# ---------------------------------------------------------------------------


def _render_row_of(browser: BindingBrowser, selectable_index: int) -> int:
    """Return the render line index whose ``selectable_index`` matches."""
    for i, (_segs, sel) in enumerate(browser._render):
        if sel == selectable_index:
            return i
    raise AssertionError(f"no render row for selectable {selectable_index}")


def _left_press(row: int, col: int = 2) -> MouseEvent:
    return MouseEvent(col=col, row=row, button=MouseButton.LEFT, kind=MouseKind.PRESS)


def _click_row(
    browser: BindingBrowser, selectable_index: int, col: int = 2
) -> MouseEvent:
    """Mouse event targeting the render line of a selectable row (offset-aware)."""
    idx = _render_row_of(browser, selectable_index)
    return _left_press(idx - browser._offset + 2, col)


def _click_render_line(
    browser: BindingBrowser, render_index: int, col: int = 2
) -> MouseEvent:
    """Mouse event targeting an arbitrary render line (offset-aware)."""
    return _left_press(render_index - browser._offset + 2, col)


class TestBindingBrowserMouse:
    def _browser(self, groups=None, inner_height=12):
        owner = _Owner()
        owner.hit = None
        rows = owner.get_executable_bindings()
        closed: list[bool] = []
        browser = BindingBrowser(
            inner_width=40,
            inner_height=inner_height,
            on_toggle=lambda: closed.append(True),
        )
        browser.resize((80, 24))
        browser.set_groups(groups or [("Panel", rows)])
        return browser, owner, closed

    def test_left_click_moves_cursor_without_invoking_or_dismissing(self) -> None:
        browser, owner, closed = self._browser()
        assert browser._cursor == 0
        assert browser.handle_mouse(_click_row(browser, 1)) is True
        assert browser._cursor == 1
        assert owner.hit is None
        assert closed == []

    def test_double_click_activates_and_dismisses(self) -> None:
        browser, owner, closed = self._browser()
        ev = _click_row(browser, 0)
        assert browser.handle_mouse(ev) is True
        assert owner.hit is None
        assert browser.handle_mouse(ev) is True
        assert owner.hit == "alpha"
        assert closed == [True]

    def test_double_click_requires_same_index(self) -> None:
        browser, owner, closed = self._browser()
        ev_a = _click_row(browser, 0)
        ev_b = _click_row(browser, 1)
        assert browser.handle_mouse(ev_a) is True
        assert browser.handle_mouse(ev_b) is True
        assert owner.hit is None
        assert closed == []

    def test_double_click_requires_recent_second_press(self) -> None:
        browser, owner, closed = self._browser()
        ev = _click_row(browser, 0)
        with mock.patch(
            "pigit.termui.viewport_hit.time.monotonic",
            side_effect=[100.0, 100.5],
        ):
            browser.handle_mouse(ev)
            browser.handle_mouse(ev)
        assert owner.hit is None
        assert closed == []

    def test_double_click_at_exact_threshold_activates(self) -> None:
        """Two presses exactly ``DOUBLE_CLICK_MS`` apart still count (<=)."""
        browser, owner, closed = self._browser()
        ev = _click_row(browser, 0)
        # Base at 0.0 so ``now - last`` is exactly the threshold in float
        # (a 100.0 -> 100.4 pair would round above 0.4).
        threshold = DOUBLE_CLICK_MS / 1000.0
        with mock.patch(
            "pigit.termui.viewport_hit.time.monotonic",
            side_effect=[0.0, threshold],
        ):
            browser.handle_mouse(ev)
            browser.handle_mouse(ev)
        assert owner.hit == "alpha"
        assert closed == [True]

    def test_double_click_just_over_threshold_is_single(self) -> None:
        """A press one epsilon past the window must not activate."""
        browser, owner, closed = self._browser()
        ev = _click_row(browser, 0)
        threshold = DOUBLE_CLICK_MS / 1000.0
        with mock.patch(
            "pigit.termui.viewport_hit.time.monotonic",
            side_effect=[0.0, threshold + 0.001],
        ):
            browser.handle_mouse(ev)
            browser.handle_mouse(ev)
        assert owner.hit is None
        assert closed == []

    def test_activate_clears_double_click_state(self) -> None:
        browser, owner, closed = self._browser()
        ev = _click_row(browser, 0)
        browser.handle_mouse(ev)
        browser.handle_mouse(ev)
        assert owner.hit == "alpha"
        owner.hit = None
        # Third press must be a plain single click again.
        browser.handle_mouse(ev)
        assert owner.hit is None
        assert closed == [True]

    def test_set_groups_resets_double_click_state(self) -> None:
        browser, owner, closed = self._browser()
        ev = _click_row(browser, 0)
        browser.handle_mouse(ev)
        browser.handle_mouse(ev)
        assert owner.hit == "alpha"
        owner.hit = None
        # Reopening the popup replaces groups; stale double-click state is gone.
        browser.set_groups([("Panel", owner.get_executable_bindings())])
        browser.handle_mouse(ev)
        assert owner.hit is None
        assert closed == [True]

    def test_resize_clears_double_click_state(self) -> None:
        browser, owner, closed = self._browser()
        browser.handle_mouse(_click_row(browser, 0))
        # A terminal resize inside the click window must not let the next
        # press pair with the pre-resize one (plan §3.2).
        browser.resize((100, 30))
        browser.handle_mouse(_click_row(browser, 0))
        assert owner.hit is None
        assert closed == []

    def test_click_on_header_blank_or_wrap_consumed_without_action(self) -> None:
        browser, owner, closed = self._browser()
        # Group header is the first render line (content row 1).
        assert browser.handle_mouse(_click_render_line(browser, 0)) is True
        assert browser._cursor == 0
        assert owner.hit is None
        assert closed == []
        # Wrapped continuation line is not selectable.
        wrap = next(
            i
            for i in range(1, len(browser._render))
            if browser._render[i][1] is None and browser._render[i - 1][1] is not None
        )
        assert browser.handle_mouse(_click_render_line(browser, wrap)) is True
        assert browser._cursor == 0
        assert owner.hit is None
        assert closed == []

    def test_click_after_wheel_keeps_cursor_visible(self) -> None:
        browser, _owner, _closed = self._browser(inner_height=5)
        for _ in range(5):
            browser.handle_mouse(
                MouseEvent(1, 1, MouseButton.WHEEL_DOWN, MouseKind.PRESS)
            )
        assert browser._offset > 0
        last = len(browser._selectable) - 1
        assert browser.handle_mouse(_click_row(browser, last)) is True
        assert browser._cursor == last
        assert browser._cursor_primary_render_index() >= browser._offset
        assert (
            browser._cursor_primary_render_index() < browser._offset + browser._scroll_h
        )

    def test_double_click_dismiss_only_row_only_closes(self) -> None:
        owner = _Owner()
        rows = owner.get_executable_bindings()
        help_row = next(r for r in rows if r.action.endswith(".help"))
        universal = replace(help_row, action="universal.help")
        browser, _owner, closed = self._browser(groups=[("Global", [universal])])
        owner.hit = None
        ev = _click_row(browser, 0)
        browser.handle_mouse(ev)
        browser.handle_mouse(ev)
        assert closed == [True]
        assert owner.hit is None

    def test_release_ignored(self) -> None:
        browser, _owner, _closed = self._browser()
        ev = MouseEvent(col=2, row=2, button=MouseButton.LEFT, kind=MouseKind.RELEASE)
        assert browser.handle_mouse(ev) is False
        assert browser._cursor == 0
