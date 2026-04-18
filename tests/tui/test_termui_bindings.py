# -*- coding: utf-8 -*-
"""Tests for ``pigit.termui.bindings.resolve_key_handlers``."""

import pytest

from pigit.termui._bindings import BindingError, resolve_key_handlers


class _Owner:
    BINDINGS = None

    def ok(self) -> None:
        pass


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
