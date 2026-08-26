# -*- coding: utf-8 -*-
"""
Module: tests/termui/test_public_api_exports.py
Description: Contract tests for pigit.termui root public API.
Author: Zev
Date: 2026-08-20
"""

from __future__ import annotations

# Tier-0 names that must remain on pigit.termui through the migration.
REQUIRED_ROOT: frozenset[str] = frozenset(
    {
        "Application",
        "ComponentRoot",
        "Component",
        "ComponentError",
        "ExitEventLoop",
        "bind_signals",
        "render_child",
        "resolve_presentation_leaf",
        "is_on_visible_paint_path",
        "Binding",
        "BindingError",
        "bind_action",
        "collect_action_bindings",
        "set_key_overrides",
        "keys",
        "palette",
        "Theme",
        "DEFAULT_THEME",
        "get_theme",
        "set_theme",
        "EventType",
        "EVT_GOTO",
        "EVT_SELECTION_CHANGED",
        "LayerKind",
        "OverlayDispatchResult",
        "ToastPosition",
        "FeedbackKind",
        "Surface",
        "Segment",
        "MouseButton",
        "MouseEvent",
        "MouseKind",
        "AsyncTask",
        "run_async",
        "show_toast",
        "show_sheet",
        "dismiss_sheet",
        "dismiss_toast",
        "show_badge",
        "get_badge",
        "get_badge_signal",
        "show_spinner",
        "hide_spinner",
        "exec_external",
        "request_render",
        "by_id",
        "get_registry",
        "get_focus_manager",
        "get_renderer",
        "get_renderer_strict",
    }
)

# Must leave root by end of Phase 1 (primitives) / Phase 2 (widgets) / Phase 3 (syntax/renderer).
FORBIDDEN_ON_ROOT: frozenset[str] = frozenset(
    {
        "Toast",
        "Sheet",
        "Popup",
        "AlertDialog",
        "AlertDialogBody",
        "HelpPanel",
        "HelpEntry",
        "plain",
        "BoxFrame",
        "parse_ansi_line",
        "tokenize_with_positions",
        "merge_ranges",
        "SyntaxTokenizer",
        "Renderer",
    }
)


def test_required_root_exports_present():
    from pigit import termui

    for name in sorted(REQUIRED_ROOT):
        assert hasattr(termui, name), f"missing required root export: {name}"
        assert name in termui.__all__, f"{name} not in __all__"


def test_root_all_matches_required_exactly():
    from pigit import termui

    assert set(termui.__all__) == REQUIRED_ROOT


def test_forbidden_root_exports_still_documented():
    """Phase 0: constant must stay disjoint from REQUIRED_ROOT."""
    assert REQUIRED_ROOT.isdisjoint(FORBIDDEN_ON_ROOT)


PRIMITIVES_LEFT_ROOT = frozenset(
    {
        "plain",
        "BoxFrame",
        "parse_ansi_line",
        "tokenize_with_positions",
        "merge_ranges",
    }
)


def test_primitives_symbols_not_on_root():
    from pigit import termui

    for name in sorted(PRIMITIVES_LEFT_ROOT):
        assert name not in termui.__all__
        assert not hasattr(termui, name)


WIDGET_LEFT_ROOT = frozenset(
    {
        "Toast",
        "Sheet",
        "Popup",
        "AlertDialog",
        "AlertDialogBody",
        "HelpPanel",
        "HelpEntry",
    }
)


def test_widget_classes_not_on_root():
    from pigit import termui

    for name in sorted(WIDGET_LEFT_ROOT):
        assert name not in termui.__all__
        assert not hasattr(termui, name)


def test_syntax_and_renderer_not_on_root():
    from pigit import termui

    assert "SyntaxTokenizer" not in termui.__all__
    assert "Renderer" not in termui.__all__
    from pigit.termui.syntax import SyntaxTokenizer
    from pigit.termui.renderer import Renderer

    assert SyntaxTokenizer is not None
    assert Renderer is not None
