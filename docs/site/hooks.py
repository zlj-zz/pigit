"""
Module: docs/site/hooks.py
Description: MkDocs hooks — sync demo assets from docs/resources into pages/assets.
Author: Zev
Date: 2026-08-31
"""

from __future__ import annotations

import shutil
from pathlib import Path


def on_pre_build(config) -> None:
    """Copy demo GIFs from docs/resources into the MkDocs pages assets dir."""
    site_dir = Path(__file__).resolve().parent
    repo_root = site_dir.parent.parent
    src_dir = repo_root / "docs" / "resources"
    dest_dir = site_dir / "pages" / "assets"
    dest_dir.mkdir(parents=True, exist_ok=True)

    for name in ("demo_interaction.gif", "demo.gif"):
        src = src_dir / name
        if src.is_file():
            shutil.copy2(src, dest_dir / name)
