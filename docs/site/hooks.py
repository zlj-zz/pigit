"""
Module: docs/site/hooks.py
Description: MkDocs hooks — sync demo GIFs and Archify diagrams into pages/assets.
Author: Zev
Date: 2026-08-31
"""

from __future__ import annotations

import shutil
from pathlib import Path

# (source relative to docs/, destination under pages/assets/)
_SYNC_MAP = (
    ("resources/demo_interaction.gif", "demo_interaction.gif"),
    ("resources/demo.gif", "demo.gif"),
    ("resources/architecture-runtime.png", "archify/runtime-preview.png"),
    ("resources/sequencer-lifecycle.png", "archify/sequencer-preview.png"),
    (
        "archify/pigit-runtime.architecture.html",
        "archify/pigit-runtime.architecture.html",
    ),
    (
        "archify/pigit-sequencer.lifecycle.html",
        "archify/pigit-sequencer.lifecycle.html",
    ),
    (
        "archify/pigit-palette.sequence.html",
        "archify/pigit-palette.sequence.html",
    ),
)


def on_pre_build(config) -> None:
    """Copy demo GIFs and Archify artifacts into the MkDocs pages assets dir."""
    site_dir = Path(__file__).resolve().parent
    docs_dir = site_dir.parent
    dest_root = site_dir / "pages" / "assets"

    for src_rel, dest_rel in _SYNC_MAP:
        src = docs_dir / src_rel
        if not src.is_file():
            continue
        dest = dest_root / dest_rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
