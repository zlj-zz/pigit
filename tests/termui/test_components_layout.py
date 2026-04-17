# -*- coding: utf-8 -*-
"""
Module: tests/termui/test_components_layout.py
Description: Tests for Container layout mode.
Author: Zev
Date: 2026-04-17
"""

from pigit.termui.components import Container, Component
from pigit.termui.layout import FlexRow
from pigit.termui.surface import Surface


class _Leaf(Component):
    NAME = "leaf"

    def __init__(self):
        super().__init__()
        self.render_calls = 0

    def fresh(self):
        pass

    def _render_surface(self, surface):
        self.render_calls += 1


def test_container_layout_mode_renders_all_children():
    a, b = _Leaf(), _Leaf()
    cont = Container({"main": a, "b": b}, layout=FlexRow([a, b], [1, 1]))
    cont.resize((10, 5))
    s = Surface(10, 5)
    cont._render_surface(s)
    assert a.render_calls == 1
    assert b.render_calls == 1


def test_container_layout_mode_uses_layout_children_order():
    a, b = _Leaf(), _Leaf()
    cont = Container({"main": b, "a": a}, layout=FlexRow([b, a], [1, 1]))
    cont.resize((10, 5))
    s = Surface(10, 5)
    cont._render_surface(s)
    assert a.render_calls == 1
    assert b.render_calls == 1


def test_container_legacy_mode_renders_only_activated():
    a, b = _Leaf(), _Leaf()
    cont = Container({"main": a, "b": b})
    cont.resize((10, 5))
    s = Surface(10, 5)
    cont._render_surface(s)
    assert a.render_calls == 1
    assert b.render_calls == 0


def test_container_layout_mode_resize_sets_coords():
    a, b = _Leaf(), _Leaf()
    cont = Container({"main": a, "b": b}, x=3, y=5, layout=FlexRow([a, b], [1, 1]))
    cont.resize((10, 4))
    assert a.x == 3
    assert a.y == 5
    assert b.x == 8
    assert b.y == 5
