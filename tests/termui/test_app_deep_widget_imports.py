# -*- coding: utf-8 -*-
"""
Module: tests/termui/test_app_deep_widget_imports.py
Description: Forbid pigit.termui.widgets.<leaf> imports in app*.py.
Author: Zev
Date: 2026-08-20
"""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "pigit"


def _deep_widget_imports() -> set[tuple[str, str]]:
    found: set[tuple[str, str]] = set()
    for path in sorted(ROOT.glob("app*.py")):
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom):
                continue
            mod = node.module or ""
            if mod.startswith("pigit.termui.widgets."):
                found.add((path.name, mod))
    return found


def test_app_does_not_import_widget_leaf_modules():
    found = _deep_widget_imports()
    assert found == set(), f"deep widget imports: {found}"
