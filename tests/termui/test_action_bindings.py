# -*- coding: utf-8 -*-
"""
Module: tests/termui/test_action_bindings.py
Description: Tests for the @bind_action action-binding mechanism.
Author: Zev
Date: 2026-08-14
"""

from __future__ import annotations

import pytest

from pigit.termui import (
    BindingError,
    Component,
    bind_action,
    collect_action_bindings,
)


class _Panel(Component):
    @bind_action("next", "j", "down", desc="Navigate", tip="Navigate")
    def next(self, step: int = 1) -> str:
        return "next"

    @bind_action("checkout", "c", desc="Checkout", tip="Checkout")
    def checkout(self) -> str:
        return "checkout"

    @bind_action("delete", "d", desc="Delete")
    def delete(self) -> str:
        return "delete"


def test_collect_action_bindings_shape():
    bindings = collect_action_bindings(_Panel)
    by_action = {b.action: b for b in bindings}
    assert set(by_action) == {"next", "checkout", "delete"}

    nxt = by_action["next"]
    assert nxt.keys == ("j", "down")
    assert nxt.desc == "Navigate"
    assert nxt.tip == "Navigate"
    assert nxt.target == "next"
    assert by_action["delete"].tip is None


def test_action_keys_resolved_into_key_handlers():
    panel = _Panel()
    assert panel._key_handlers["j"] is not None
    assert panel._key_handlers["down"] is not None
    assert panel._key_handlers["j"]() == "next"
    assert panel._key_handlers["c"]() == "checkout"


def test_multi_key_same_handler():
    panel = _Panel()
    assert panel._key_handlers["j"] is panel._key_handlers["down"]


def test_parent_bindings_collected_before_subclass():
    class _Child(_Panel):
        @bind_action("rename", "r", desc="Rename")
        def rename(self) -> str:
            return "rename"

    bindings = collect_action_bindings(_Child)
    assert [b.action for b in bindings] == ["next", "checkout", "delete", "rename"]


def test_callable_desc_and_tip_when():
    class _Dynamic(Component):
        @bind_action(
            "stash",
            "z",
            desc=lambda self: f"Stash ({self._scope})",
            tip="Stash",
            tip_when=lambda self: self._enabled,
        )
        def stash(self) -> str:
            return "stash"

    panel = _Dynamic()
    binding = panel._action_bindings[0]
    panel._scope = "local"
    panel._enabled = True
    assert binding.desc(panel) == "Stash (local)"
    assert binding.tip_when(panel) is True


def test_tip_when_hides_footer_not_help():
    class _Gated(Component):
        def __init__(self) -> None:
            self._show_tip = False
            super().__init__()

        @bind_action(
            "stage",
            "s",
            desc="Stage file",
            tip="Stage",
            tip_when=lambda self: self._show_tip,
        )
        def stage(self) -> None:
            pass

    panel = _Gated()
    help_entries = panel.get_help_entries()
    assert any(desc == "Stage file" for _, desc in help_entries)
    assert panel.get_footer_entries() == []

    panel._show_tip = True
    assert panel.get_footer_entries() == [("s", "Stage")]


def test_application_resolves_bind_action():
    from pigit.termui._application import Application

    class _App(Application):
        keymap_namespace = "universal"

        @bind_action("help", "?", desc="Help")
        def toggle_help(self) -> str:
            return "help"

        @bind_action("goto_status", "1", desc="Status tab")
        def goto_status(self) -> str:
            return "status"

    app = _App()
    assert app._key_handlers["?"]() == "help"
    assert app._key_handlers["1"]() == "status"


def test_configurable_false_ignores_override():
    from pigit.termui import set_key_overrides

    class _Locked(Component):
        @bind_action("locked", "x", desc="Locked", configurable=False)
        def locked(self) -> str:
            return "locked"

    set_key_overrides({"locked": "y"})
    panel = _Locked()
    # override is ignored for non-configurable bindings
    assert panel._key_handlers["x"]() == "locked"
    assert "y" not in panel._key_handlers
    set_key_overrides({})


def test_capture_key_intercepts_before_bindings():
    class _Capture(Component):
        def __init__(self):
            super().__init__()
            self.capturing = False
            self.acted = False

        def capture_key(self, key: str) -> bool:
            return self.capturing

        @bind_action("act", "a", desc="Action")
        def act(self) -> None:
            self.acted = True

    c = _Capture()
    # Not capturing -> binding fires.
    assert c._handle_event("a") is True
    assert c.acted is True
    # Capturing -> capture_key consumes the key, binding does not fire.
    c.acted = False
    c.capturing = True
    assert c._handle_event("a") is True
    assert c.acted is False


def test_duplicate_key_different_targets_raises():
    class _Dup(Component):
        @bind_action("one", "a", desc="One")
        def one(self) -> None:
            pass

        @bind_action("two", "a", desc="Two")
        def two(self) -> None:
            pass

    with pytest.raises(BindingError) as exc:
        _Dup()
    assert exc.value.semantic_key == "a"
    assert exc.value.first_target == "one"
    assert exc.value.second_target == "two"


def test_duplicate_key_same_handler_is_allowed():
    class _Child(_Panel):
        @bind_action("next", "j", desc="Next again")
        def next(self, step: int = 1) -> str:
            return "next"

    # Re-decorating "j" on an overridden method resolves to the same handler,
    # so it is a no-op rather than a conflict.
    panel = _Child()
    assert panel._key_handlers["j"]() == "next"


def test_bindings_conflict_with_action_raises():
    class _Conf(Component):
        BINDINGS = [("x", "bound")]

        @bind_action("act", "x", desc="Action")
        def act(self) -> None:
            pass

        def bound(self) -> None:
            pass

    with pytest.raises(BindingError) as exc:
        _Conf()
    assert exc.value.semantic_key == "x"
    assert exc.value.first_target == "bound"
    assert exc.value.second_target == "act"
