# -*- coding: utf-8 -*-
"""
Module: tests/app/test_import_ratchets.py
Description: Ratchet tests for app-layer imports and palette references.
Author: Zev
Date: 2026-08-26
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2] / "pigit"


# ---- deep widget imports ----


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


# ---- private termui imports ----

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


# ---- direct palette color references ----

# Files that are allowed to reference palette directly
_EXEMPT_FILES = {
    "app_theme.py",
    # Chart/lane colors are intentionally raw palette constants (not semantic roles)
    "app_commit.py",
    "app_contribution_graph.py",
}

# Allowed palette attributes (style flags only)
_ALLOWED_ATTR_PREFIXES = ("STYLE_",)


def _collect_app_files() -> list[Path]:
    files = []
    for f in ROOT.glob("app_*.py"):
        if f.name not in _EXEMPT_FILES:
            files.append(f)
    for f in ROOT.glob("handlers/*.py"):
        files.append(f)
    # picker_app.py is also app-layer
    picker = ROOT / "picker_app.py"
    if picker.exists():
        files.append(picker)
    return sorted(files)


def _find_palette_violations(file_path: Path) -> list[str]:
    """Return list of violation messages for a single file."""
    source = file_path.read_text()
    tree = ast.parse(source)
    violations = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            # Check for palette.XXX references
            if isinstance(node.value, ast.Name) and node.value.id == "palette":
                attr = node.attr
                if not any(attr.startswith(p) for p in _ALLOWED_ATTR_PREFIXES):
                    violations.append(f"{file_path.name}:{node.lineno}: palette.{attr}")

    return violations


@pytest.mark.parametrize("file_path", _collect_app_files(), ids=lambda p: p.name)
def test_no_direct_palette_color_refs(file_path: Path) -> None:
    violations = _find_palette_violations(file_path)
    if violations:
        msg = "\n  ".join(
            [f"Direct palette color refs in {file_path.name}:"] + violations
        )
        pytest.fail(msg)
