# -*- coding: utf-8 -*-
"""
Module: tests/termui/test_tab_view_goto.py
Description: TabView does not consume EVT_GOTO; app owns goto routing.
Author: Zev
Date: 2026-08-25
"""

from __future__ import annotations

from pigit.termui import Component
from pigit.termui.containers import TabView


class _Panel(Component):
    def __init__(self, id: str) -> None:
        super().__init__(id=id)


def test_tab_view_does_not_intercept_goto_bubble():
    """TabView has no on_event; EVT_GOTO bubbles to Application."""
    assert "on_event" not in TabView.__dict__


def test_route_to_still_switches_tabs():
    a = _Panel("status")
    b = _Panel("branch")
    tv = TabView(children=[a, b], start="status")
    assert tv.route_to("branch") is b
    assert tv.visible is b


def test_presentation_child_is_active_tab():
    a = _Panel("status")
    b = _Panel("branch")
    tv = TabView(children=[a, b], start="status")
    assert tv.presentation_child is a
    tv.route_to("branch")
    assert tv.presentation_child is b
