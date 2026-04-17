# -*- coding: utf-8 -*-
"""
Module: tests/termui/test_root.py
Description: Tests for pigit.termui.root.
Author: Zev
Date: 2026-04-17
"""

import pytest
from unittest.mock import MagicMock

from pigit.termui.components import Component
from pigit.termui.root import ComponentRoot
from pigit.termui.overlay_kinds import OverlayDispatchResult, OverlayKind


class DummyBody(Component):
    NAME = "dummy"

    def _render_surface(self, surface):
        pass

    def fresh(self):
        pass


class TestComponentRoot:
    def test_body_parent_is_root(self):
        body = DummyBody()
        root = ComponentRoot(body)
        assert root.body is body
        assert body.parent is root

    def test_overlay_kind_none_by_default(self):
        root = ComponentRoot(DummyBody())
        assert not root.has_overlay_open()

    def test_begin_end_popup_session(self):
        root = ComponentRoot(DummyBody())
        popup = MagicMock()
        popup.open = True
        root.begin_popup_session(popup)
        assert root.has_overlay_open()
        assert root.overlay_kind is OverlayKind.POPUP
        assert root._active_popup is popup
        root.end_popup_session()
        popup.hide.assert_not_called()
        assert not root.has_overlay_open()
        assert root.overlay_kind is OverlayKind.NONE
        assert root._active_popup is None

    def test_handle_event_modal_intercepts(self):
        root = ComponentRoot(DummyBody())
        body = root.body
        body._handle_event = MagicMock()
        popup = MagicMock()
        popup.open = True
        popup.dispatch_overlay_key.return_value = OverlayDispatchResult.HANDLED_EXPLICIT
        root.begin_popup_session(popup)
        root._handle_event("k")
        popup.dispatch_overlay_key.assert_called_once_with("k")
        body._handle_event.assert_not_called()

    def test_handle_event_passthrough_to_body(self):
        root = ComponentRoot(DummyBody())
        body = root.body
        body._handle_event = MagicMock()
        root._handle_event("k")
        body._handle_event.assert_called_once_with("k")

    def test_force_close_overlay_after_error(self):
        root = ComponentRoot(DummyBody())
        popup = MagicMock()
        popup.open = True
        root.begin_popup_session(popup)
        root.force_close_overlay_after_error()
        popup.hide.assert_called_once()
        assert not root.has_overlay_open()
        assert root.overlay_kind is OverlayKind.NONE
        assert root._active_popup is None

    def test_accept_forwards_to_body(self):
        root = ComponentRoot(DummyBody())
        root.body.accept = MagicMock()
        root.accept("goto", target="x")
        root.body.accept.assert_called_once_with("goto", target="x")

    def test_fresh_does_not_raise(self):
        root = ComponentRoot(DummyBody())
        root.fresh()
