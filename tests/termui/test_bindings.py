# -*- coding: utf-8 -*-
"""Tests for pigit.termui._bindings."""

from __future__ import annotations

import pytest

from pigit.termui._bindings import (
    BindingError,
    bind_keys,
    list_bindings,
    resolve_key_handlers,
    resolve_key_handlers_merged,
)
from pigit.termui._component_base import Component


class _Owner:
    BINDINGS = None

    def ok(self) -> None:
        pass


# --- resolve_key_handlers ---


def test_resolve_string_method():
    owner = _Owner()
    handlers = resolve_key_handlers(
        owner,
        [("a", "ok")],
    )
    assert handlers["a"].__self__ is owner
    assert handlers["a"].__func__ is _Owner.ok


def test_resolve_callable():
    owner = _Owner()
    called = []

    def cb() -> None:
        called.append(1)

    handlers = resolve_key_handlers(owner, [("b", cb)])
    handlers["b"]()
    assert called == [1]


def test_resolve_missing_method_name_raises():
    owner = _Owner()
    with pytest.raises(BindingError, match="not_a_method"):
        resolve_key_handlers(owner, [("x", "not_a_method")])


def test_resolve_non_callable_attribute_raises():
    owner = _Owner()
    owner.bad = 3  # type: ignore[attr-defined]
    with pytest.raises(BindingError, match="not callable"):
        resolve_key_handlers(owner, [("x", "bad")])


def test_resolve_invalid_target_type_raises():
    owner = _Owner()
    with pytest.raises(TypeError, match="str or callable"):
        resolve_key_handlers(owner, [("x", 99)])  # type: ignore[list-item]


# --- resolve_key_handlers_merged / bind_keys / list_bindings ---


class _Base(Component):
    NAME = "x"
    BINDINGS = [("x", "on_x")]

    def __init__(self) -> None:
        super().__init__()
        self.seen: list = []

    def fresh(self) -> None:
        pass

    def _render_surface(self, surface):
        pass

    def on_x(self) -> None:
        self.seen.append("class")


class _WithDeco(_Base):
    @bind_keys("a", "b")
    def deco_dup(self) -> None:
        """Doc line for deco."""
        self.seen.append("deco")


class _Conflict(_Base):
    BINDINGS = [("a", "on_x")]

    @bind_keys("a")
    def other(self) -> None:
        self.seen.append("other")


def test_merge_order_decorator_before_class_bindings():
    owner = _WithDeco()
    h = resolve_key_handlers_merged(owner, type(owner), owner.BINDINGS)
    h["a"]()
    h["b"]()
    h["x"]()
    assert owner.seen == ["deco", "deco", "class"]


def test_duplicate_same_callable_deduped():
    class _Dup(Component):
        NAME = "d"
        BINDINGS = [("p", "press")]

        @bind_keys("p")
        def press(self) -> None:
            self.n = 1

        def fresh(self) -> None:
            pass

        def _render_surface(self, surface):
            pass

    o = _Dup()
    h = resolve_key_handlers_merged(o, type(o), o.BINDINGS)
    assert len(h) == 1
    h["p"]()
    assert o.n == 1


def test_conflict_raises_binding_error_with_context():
    with pytest.raises(BindingError) as ei:
        _Conflict()
    err = ei.value
    assert err.semantic_key == "a"
    assert err.first_target is not None
    assert err.second_target is not None
    assert err.owner_class_name == "_Conflict"


def test_list_bindings_matches_merge():
    owner = _WithDeco()
    merged = list_bindings(owner, type(owner))
    keys = [k for k, _ in merged]
    assert keys[:2] == ["a", "b"]
    assert keys[-1] == "x"


def test_get_help_entries_keys_align_with_list_bindings():
    owner = _WithDeco()
    from pigit.termui._bindings import list_bindings as lb

    help_rows = owner.get_help_entries()
    bind_keys = [k for k, _ in lb(owner, type(owner))]
    help_keys = [k for k, _ in help_rows]
    assert help_keys == bind_keys
