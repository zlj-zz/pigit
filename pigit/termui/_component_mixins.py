# -*- coding: utf-8 -*-
"""
Module: pigit/termui/_component_mixins.py
Description: Mixin classes for TUI components.
Author: Zev
Date: 2026-04-19
"""

from __future__ import annotations


class LazyLoadMixin:
    """Defer expensive :meth:`fresh` until the panel is activated.

    Inactive panels show a one-line placeholder until first shown, so startup
    ``resize`` avoids running git for every tab. Pair with a container that
    calls :meth:`fresh` when switching to the active child (:meth:`TabView.switch_child`).
    """

    _panel_loaded: bool = False

    def resize(self, size: tuple[int, int]) -> None:
        self._size = size
        if self.is_activated():
            self.fresh()
            self._panel_loaded = True
        elif not self._panel_loaded:
            self.set_content(["Loading..."])
            self.curr_no = 0
            self._r_start = 0
