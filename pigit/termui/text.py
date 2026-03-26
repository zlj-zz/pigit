# -*- coding: utf-8 -*-
"""
Module: pigit/termui/text.py
Description: Display width and ANSI stripping — single source imports ``pigit.tui.utils``.
Author: Project Team
Date: 2026-03-26
"""

from __future__ import annotations

# Single source of truth (technical_unified_termui_refactor §5): do not duplicate algorithms.
from pigit.tui.utils import get_width, plain

__all__ = ["get_width", "plain"]
