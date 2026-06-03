"""Prevent app-layer files from directly referencing palette color constants.

Widgets and app_theme.py are exempt. Only STYLE_* flags are allowed.
"""

import ast
from pathlib import Path

import pytest


# Files that are allowed to reference palette directly
_EXEMPT_FILES = {
    "app_theme.py",
    # Chart/lane colors are intentionally raw palette constants (not semantic roles)
    "app_commit.py",
    "app_contribution_graph.py",
}

# Allowed palette attributes (style flags only)
_ALLOWED_ATTR_PREFIXES = ("STYLE_",)

# Directories to scan
_APP_DIRS = [
    Path(__file__).parent.parent / "pigit",
]


def _find_violations(file_path: Path) -> list[str]:
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


def _collect_app_files() -> list[Path]:
    files = []
    for root_dir in _APP_DIRS:
        for f in root_dir.glob("app_*.py"):
            if f.name not in _EXEMPT_FILES:
                files.append(f)
        for f in root_dir.glob("handlers/*.py"):
            files.append(f)
        # picker_app.py is also app-layer
        picker = root_dir / "picker_app.py"
        if picker.exists():
            files.append(picker)
    return sorted(files)


@pytest.mark.parametrize("file_path", _collect_app_files(), ids=lambda p: p.name)
def test_no_direct_palette_color_refs(file_path: Path) -> None:
    violations = _find_violations(file_path)
    if violations:
        msg = "\n  ".join([f"Direct palette color refs in {file_path.name}:"] + violations)
        pytest.fail(msg)
