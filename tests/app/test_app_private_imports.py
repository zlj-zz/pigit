# -*- coding: utf-8 -*-
"""
Module: tests/app/test_app_private_imports.py
Description: Ratchet test for private pigit.termui._* imports in app*.py modules.
Author: Zev
Date: 2026-08-19
"""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "pigit"
ALLOWED: set[tuple[str, str, str]] = set()


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
