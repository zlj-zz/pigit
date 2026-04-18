# -*- coding: utf-8 -*-
"""
Module: tests/termui/test_components_overlay.py
Description: Tests for Toast, Sheet, HelpPanel and overlay components.
Author: Zev
Date: 2026-04-18
"""

import pytest
from unittest.mock import MagicMock

from pigit.termui.components import Component
from pigit.termui.components_overlay import (
    AlertDialogBody,
    HelpEntry,
    HelpPanel,
    Popup,
    Sheet,
    Toast,
)
from pigit.termui.overlay_kinds import OverlayDispatchResult
from pigit.termui.surface import Surface


class _Leaf(Component):
    NAME = "leaf"

    def _render_surface(self, surface):
        pass

    def fresh(self):
        pass


class TestToast:
    def test_toast_render_surface(self):
        toast = Toast("Hello World", duration=5.0)
        surface = Surface(40, 10)
        toast._render_surface(surface)

        row_text = surface._rows[surface.height - 2]
        combined = "".join(c.char for c in row_text)
        assert "Hello World" in combined

    def test_toast_render_long_message_truncates(self):
        msg = "A" * 100
        toast = Toast(msg, duration=5.0)
        surface = Surface(20, 10)
        toast._render_surface(surface)

        row_text = surface._rows[surface.height - 2]
        combined = "".join(c.char for c in row_text).rstrip()
        assert len(combined) <= 18  # surface.width - 2
        assert combined == "A" * 18

    def test_toast_is_expired(self):
        clock = MagicMock(return_value=0.0)
        toast = Toast("msg", duration=2.0, clock=clock)
        assert not toast.is_expired()
        clock.return_value = 3.0
        assert toast.is_expired()

    def test_toast_dispatch_dropped(self):
        toast = Toast("msg")
        assert toast.dispatch_overlay_key("k") is OverlayDispatchResult.DROPPED_UNBOUND

    def test_toast_hide_sets_open_false(self):
        toast = Toast("msg")
        assert toast.open is True
        toast.hide()
        assert toast.open is False


class TestSheet:
    def test_sheet_render_surface_draws_child_at_bottom(self):
        child = MagicMock()
        child._render_surface = MagicMock()
        sheet = Sheet(child, height=3)
        sheet._size = (20, 3)

        surface = Surface(20, 10)
        sheet._render_surface(surface)

        child._render_surface.assert_called_once()
        sub = child._render_surface.call_args[0][0]
        # Subsurface height matches sheet size; _to_parent translates to bottom area
        assert sub.height == 3
        assert hasattr(sub, "_to_parent")

    def test_sheet_render_surface_zero_height_skips(self):
        child = MagicMock()
        sheet = Sheet(child, height=0)
        sheet._size = (20, 0)

        surface = Surface(20, 10)
        sheet._render_surface(surface)

        child._render_surface.assert_not_called()

    def test_sheet_dispatch_delegates_to_child(self):
        child = MagicMock()
        child.dispatch_overlay_key.return_value = OverlayDispatchResult.HANDLED_EXPLICIT
        sheet = Sheet(child, height=3)

        result = sheet.dispatch_overlay_key("k")
        assert result is OverlayDispatchResult.HANDLED_EXPLICIT
        child.dispatch_overlay_key.assert_called_once_with("k")

    def test_sheet_dispatch_no_child_handler_returns_dropped(self):
        child = _Leaf()
        sheet = Sheet(child, height=3)

        result = sheet.dispatch_overlay_key("k")
        assert result is OverlayDispatchResult.DROPPED_UNBOUND

    def test_sheet_resize_sets_size_and_child_size(self):
        child = MagicMock()
        sheet = Sheet(child, height=6)
        sheet.resize((40, 20))

        assert sheet._size == (40, 6)
        child.resize.assert_called_once_with((40, 6))

    def test_sheet_resize_clamps_to_half_height(self):
        child = MagicMock()
        sheet = Sheet(child, height=100)
        sheet.resize((40, 20))

        assert sheet._size == (40, 10)
        child.resize.assert_called_once_with((40, 10))

    def test_sheet_hide_sets_open_false(self):
        child = _Leaf()
        sheet = Sheet(child, height=3)
        assert sheet.open is True
        sheet.hide()
        assert sheet.open is False


class TestHelpPanel:
    def test_help_panel_render_bindings(self):
        panel = HelpPanel()
        panel.set_entries([("j", "down"), ("k", "up")])
        surface = Surface(60, 20)
        panel.resize((60, 20))
        panel._render_surface(surface)

        # Frame should have drawn a border; content rows should include bindings.
        row_text = surface._rows[2]
        combined = "".join(c.char for c in row_text)
        assert "j" in combined or "down" in combined

    def test_help_panel_scroll_down_clamps(self):
        panel = HelpPanel()
        panel.set_entries([("a", "A")])
        panel.scroll_down()
        assert panel._offset == 0

    def test_help_panel_scroll_up_clamps_at_zero(self):
        panel = HelpPanel()
        # Need more entries than _scroll_h so scroll_down advances
        panel.set_entries(
            [("a", "A"), ("b", "B"), ("c", "C"), ("d", "D"),
             ("e", "E"), ("f", "F"), ("g", "G")]
        )
        start = panel._offset
        # scroll down advances (inner_h defaults to >=5, so _scroll_h >=4)
        panel.scroll_down()
        panel.scroll_down()
        panel.scroll_down()
        assert panel._offset > start
        # scroll up retreats to zero
        while panel._offset > 0:
            panel.scroll_up()
        assert panel._offset == 0
        panel.scroll_up()
        assert panel._offset == 0


class TestPopup:
    def test_popup_toggle_with_session_owner(self):
        host = MagicMock()
        host.has_overlay_open.return_value = False
        host._layer_stack = MagicMock()
        host._layer_stack.top.return_value = None
        child = _Leaf()
        popup = Popup(child, session_owner=host)

        popup.toggle()

        assert popup.open is True
        host.begin_popup_session.assert_called_once_with(popup)

    def test_popup_toggle_close_when_self_is_active(self):
        host = MagicMock()
        host.has_overlay_open.return_value = True
        child = _Leaf()
        popup = Popup(child, session_owner=host)
        host._layer_stack = MagicMock()
        host._layer_stack.top.return_value = popup

        popup.toggle()

        assert popup.open is False
        host.end_popup_session.assert_called_once()

    def test_popup_dispatch_overlay_key_explicit(self):
        class _KeyChild(Component):
            NAME = "key_child"
            BINDINGS = [("x", "on_x")]

            def on_x(self):
                pass

            def _render_surface(self, surface):
                pass

            def fresh(self):
                pass

        child = _KeyChild()
        popup = Popup(child)
        result = popup.dispatch_overlay_key("x")
        assert result is OverlayDispatchResult.HANDLED_EXPLICIT

    def test_popup_fallback_overlay_key_help_toggle(self):
        class _HelpChild(Component):
            NAME = "help_child"
            TOGGLE_HELP_SEMANTIC_KEYS = ("?",)

            def _render_surface(self, surface):
                pass

            def fresh(self):
                pass

        host = MagicMock()
        host.has_overlay_open.return_value = False
        host._layer_stack = MagicMock()
        host._layer_stack.top.return_value = None
        child = _HelpChild()
        popup = Popup(child, session_owner=host)

        result = popup.dispatch_overlay_key("?")
        assert result is OverlayDispatchResult.HANDLED_IMPLICIT

    def test_popup_fallback_swallows_unbound(self):
        child = _Leaf()
        popup = Popup(child)
        result = popup.dispatch_overlay_key("z")
        assert result is OverlayDispatchResult.DROPPED_UNBOUND

    def test_popup_render_surface_not_open_skips(self):
        child = _Leaf()
        popup = Popup(child)
        popup.open = False
        surface = Surface(40, 20)
        popup._render_surface(surface)
        # No exception and child not rendered

    def test_popup_render_surface_resizes_if_needed(self):
        child = _Leaf()
        popup = Popup(child)
        popup.open = True
        popup._term_size = (0, 0)
        surface = Surface(40, 20)
        popup._render_surface(surface)
        assert popup._term_size == (40, 20)


class TestAlertDialogBody:
    def test_alert_body_builds_content_lines(self):
        body = AlertDialogBody(
            shell=MagicMock(),
            message="Test message",
            on_result=lambda x: None,
        )
        body.resize((60, 20))  # large width so footer stays on one line
        body._rebuild_frame()
        lines = body._build_content_lines()

        assert any("Test message" in line for line in lines)
        # Footer should include both OK and Cancel
        assert any("OK" in line for line in lines)
        assert any("Cancel" in line for line in lines)

    def test_alert_body_confirm_calls_shell_finish(self):
        shell = MagicMock()
        body = AlertDialogBody(
            shell=shell,
            message="m",
            on_result=lambda x: None,
        )
        body._confirm()
        shell._finish_alert.assert_called_once_with(True)
