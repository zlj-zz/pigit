# -*- coding: utf-8 -*-
"""Tests for ComponentRoot badge API."""

from __future__ import annotations

from pigit.termui._component_base import Component
from pigit.termui._root import ComponentRoot


class MockBody(Component):
    def _render_surface(self, surface):
        pass

    def _handle_event(self, key):
        pass


class TestComponentRootBadge:
    def test_badge_starts_none(self):
        body = MockBody()
        root = ComponentRoot(body)
        assert root.badge_text is None

    def test_show_badge_sets_text(self):
        body = MockBody()
        root = ComponentRoot(body)
        root.show_badge("3 staged")
        assert root.badge_text == "3 staged"

    def test_hide_badge_clears_text(self):
        body = MockBody()
        root = ComponentRoot(body)
        root.show_badge("3 staged")
        root.hide_badge()
        assert root.badge_text is None

    def test_show_badge_overwrites_previous(self):
        body = MockBody()
        root = ComponentRoot(body)
        root.show_badge("old")
        root.show_badge("new")
        assert root.badge_text == "new"
