# -*- coding: utf-8 -*-
"""
Module: tests/termui/test_public_api_exports.py
Description: Smoke test for app-facing public exports on pigit.termui.
Author: Zev
Date: 2026-08-19
"""

from __future__ import annotations


def test_app_facing_public_exports_are_importable():
    """New Phase 1a symbols are reachable from the package root."""
    from pigit import termui

    names = (
        "MouseButton",
        "MouseEvent",
        "MouseKind",
        "AsyncTask",
        "run_async",
        "plain",
        "BoxFrame",
        "parse_ansi_line",
        "render_child",
        "resolve_presentation_leaf",
        "get_focus_manager",
        "get_renderer",
    )
    for name in names:
        assert hasattr(termui, name), f"missing export: {name}"
        assert name in termui.__all__, f"{name} not listed in __all__"
