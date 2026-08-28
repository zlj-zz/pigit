"""
Module: tests/termui/test_binding_browser.py
Description: Tests for ExecutableBinding derivation and BindingBrowser cursor/invoke.
Author: Zev
Date: 2026-08-27
"""

from __future__ import annotations

from dataclasses import replace

from pigit.termui import bind_action, keys
from pigit.termui.bindings import (
    collect_action_bindings,
    derive_executable_bindings,
    derive_help_entries,
)
from pigit.termui.component import Component
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
