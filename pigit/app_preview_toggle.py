# -*- coding: utf-8 -*-
"""
Module: pigit/app_preview_toggle.py
Description: Shared preview-toggle delegation for preview-capable panels.
Author: Zev
Date: 2026-08-18
"""

from __future__ import annotations

from pigit.termui._component import Component


def invoke_preview_toggle(panel: Component) -> None:
    """Invoke the panel's registered preview-toggle callback, if any.

    Preview-capable panels expose ``_on_toggle_preview`` (set from the
    ``on_toggle_preview`` constructor argument, wired to the app's
    ``toggle_side_preview``). The ``@bind_action("toggle_preview")`` target
    delegates here so the contract lives in one place.
    """
    callback = getattr(panel, "_on_toggle_preview", None)
    if callback is not None:
        callback()
