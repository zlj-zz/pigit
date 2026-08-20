# -*- coding: utf-8 -*-
"""
Module: pigit/observe/overlay.py
Description: Overlay predicate for deferring repo refresh (MODAL|SHEET only).
Author: Zev
Date: 2026-08-20
"""

from __future__ import annotations

from typing import Any

from pigit.termui.types import LayerKind


def should_defer_repo_refresh(root: Any) -> bool:
    """Return True when a MODAL or SHEET overlay is open — never for TOAST.

    Args:
        root: ComponentRoot (or duck-typed host) exposing ``_layer_stack``.

    Returns:
        True if repo observation sinks should defer flushing.
    """
    layer_stack = getattr(root, "_layer_stack", None)
    if layer_stack is None:
        return False
    top = getattr(layer_stack, "top", None)
    if not callable(top):
        return False
    if top(LayerKind.MODAL) is not None:
        return True
    if top(LayerKind.SHEET) is not None:
        return True
    return False
