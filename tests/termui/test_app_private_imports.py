# -*- coding: utf-8 -*-
"""
Module: tests/termui/test_app_private_imports.py
Description: Ratchet test for private pigit.termui._* imports in app*.py modules.
Author: Zev
Date: 2026-08-19
"""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "pigit"
ALLOWED = {
    ("app_inspector.py", "pigit.termui._overlay_api", "dismiss_sheet"),
    ("app_inspector.py", "pigit.termui._segment", "Segment"),
    ("app_inspector.py", "pigit.termui._surface", "Surface"),
    ("app_inspector.py", "pigit.termui._surface", "_Subsurface"),
    ("app_status.py", "pigit.termui._async_task", "run_async"),
    ("app_stash.py", "pigit.termui._mouse", "MouseButton"),
    ("app_stash.py", "pigit.termui._mouse", "MouseEvent"),
    ("app_stash.py", "pigit.termui._mouse", "MouseKind"),
    ("app_stash.py", "pigit.termui._surface", "Surface"),
    ("app_stash.py", "pigit.termui._surface", "_Subsurface"),
    ("app_commit.py", "pigit.termui._async_task", "run_async"),
    ("app.py", "pigit.termui._component", "resolve_presentation_leaf"),
    ("app.py", "pigit.termui._runtime_context", "get_focus_manager"),
    ("app.py", "pigit.termui._runtime_context", "get_renderer"),
    ("app_preview_toggle.py", "pigit.termui._component", "Component"),
    ("app_preview.py", "pigit.termui._component", "_render_child_to_surface"),
    ("app_preview.py", "pigit.termui._mouse", "MouseEvent"),
    ("app_log_graph_preview.py", "pigit.termui._ansi", "parse_ansi_line"),
    ("app_log_graph_preview.py", "pigit.termui._async_task", "AsyncTask"),
    ("app_log_graph_preview.py", "pigit.termui._async_task", "run_async"),
    ("app_log_graph_preview.py", "pigit.termui._frame", "BoxFrame"),
    ("app_log_graph_preview.py", "pigit.termui._mouse", "MouseEvent"),
    ("app_log_graph_preview.py", "pigit.termui._segment", "Segment"),
    ("app_diff.py", "pigit.termui._async_task", "AsyncTask"),
    ("app_diff.py", "pigit.termui._text", "plain"),
    ("app_contribution_graph.py", "pigit.termui._mouse", "MouseButton"),
    ("app_contribution_graph.py", "pigit.termui._mouse", "MouseKind"),
    ("app_contribution_graph.py", "pigit.termui._surface", "Surface"),
    ("app_commit_editor.py", "pigit.termui._component", "Component"),
    ("app_commit_editor.py", "pigit.termui._surface", "Surface"),
    ("app_commit_editor.py", "pigit.termui._surface", "_Subsurface"),
    ("app_chrome.py", "pigit.termui._component", "resolve_presentation_leaf"),
}


def _imports() -> set[tuple[str, str, str]]:
    """Collect private termui import tuples from every app*.py module.

    Returns:
        set[tuple[str, str, str]]: (filename, module, imported_name) tuples.
    """
    found: set[tuple[str, str, str]] = set()
    for path in sorted(ROOT.glob("app*.py")):
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and (node.module or "").startswith(
                "pigit.termui._"
            ):
                for alias in node.names:
                    found.add((path.name, node.module or "", alias.name))
    return found


def test_private_termui_imports_are_allowlisted():
    """Fail when app*.py gains or drops private pigit.termui._* imports."""
    found = _imports()
    assert found <= ALLOWED, f"new private imports: {found - ALLOWED}"
    assert ALLOWED <= found, f"stale allowlist (already gone): {ALLOWED - found}"
