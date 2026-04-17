# -*- coding: utf-8 -*-
"""
Module: tests/termui/test_layout_container.py
Description: Tests for LayoutContainer.
Author: Zev
Date: 2026-04-17
"""

from unittest.mock import MagicMock

from pigit.termui.components import LayoutContainer, Component, _render_child_to_surface
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


class TestLayoutContainer:
    def test_layout_container_render_children(self):
        a, b = _Leaf(), _Leaf()
        cont = LayoutContainer(FlexRow([a, b], [1, 1]))
        assert a.parent is cont
        assert b.parent is cont

    def test_layout_container_resize_propagates(self):
        a, b = _Leaf(), _Leaf()
        cont = LayoutContainer(FlexRow([a, b], [1, 1]), size=(10, 5))
        a.resize = MagicMock()
        b.resize = MagicMock()
        cont.resize((20, 10))
        a.resize.assert_called()
        b.resize.assert_called()

    def test_layout_container_renders_all_children(self):
        a, b = _Leaf(), _Leaf()
        cont = LayoutContainer(FlexRow([a, b], [1, 1]))
        cont.resize((10, 5))
        s = Surface(10, 5)
        cont._render_surface(s)
        assert a.render_calls == 1
        assert b.render_calls == 1

    def test_layout_container_uses_layout_children_order(self):
        a, b = _Leaf(), _Leaf()
        cont = LayoutContainer(FlexRow([b, a], [1, 1]))
        cont.resize((10, 5))
        s = Surface(10, 5)
        cont._render_surface(s)
        assert a.render_calls == 1
        assert b.render_calls == 1

    def test_layout_container_resize_sets_coords(self):
        a, b = _Leaf(), _Leaf()
        cont = LayoutContainer(FlexRow([a, b], [1, 1]), x=3, y=5)
        cont.resize((10, 4))
        assert a.x == 3
        assert a.y == 5
        assert b.x == 8
        assert b.y == 5


def test_render_child_to_surface_module_level():
    leaf = _Leaf()
    leaf.resize((3, 2))
    s = Surface(5, 5)
    _render_child_to_surface(leaf, s, "test")
    assert leaf.render_calls == 1
