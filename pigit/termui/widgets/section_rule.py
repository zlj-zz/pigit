# -*- coding: utf-8 -*-
"""
Module: pigit/termui/widgets/section_rule.py
Description: One-row section rule chrome for OptionList header slots.
Author: Zev
Date: 2026-08-26
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .. import palette
from .._runtime_context import request_render
from ..component import Component
from ..theme import get_theme
from ..wcwidth_table import wcswidth

if TYPE_CHECKING:
    from ..surface import Surface

_TAIL = "──"


class SectionRule(Component):
    """One-row rule: leading dashes, bold label, trailing ``──``.

    Follows the parent panel's presentation: brand ``fg_accent`` when the
    panel is the active focus surface, otherwise ``fg_dim``. An optional
    *status* rides after the label and turns the rule ``fg_danger`` -- the
    panel can then say "this is not right" and go on saying it, which a toast
    that expires in three seconds cannot.
    """

    def __init__(self, label: str, *, id: str | None = None) -> None:
        super().__init__(id=id)
        self._label = label
        self._status: str | None = None

    def set_status(self, status: str | None) -> None:
        """Show *status* after the label; ``None`` clears it."""
        if status == self._status:
            return
        self._status = status
        request_render()

    def _rule_fg(self) -> tuple[int, int, int]:
        """Danger while a status stands; brand accent when the owning panel
        presents; dim otherwise."""
        theme = get_theme()
        if self._status is not None:
            return theme.fg_danger
        parent = self.parent
        if parent is not None and parent.is_presentation_active():
            return theme.fg_accent
        return theme.fg_dim

    def paint(self, surface: Surface) -> None:
        w = surface.width
        if w <= 0 or surface.height <= 0:
            return
        theme = get_theme()
        label = self._label
        status = f" {self._status}" if self._status is not None else ""
        suffix = f" {label}{status} {_TAIL}"
        suffix_w = wcswidth(suffix)
        fill_w = max(0, w - suffix_w)
        rule_fg = self._rule_fg()
        if fill_w:
            surface.draw_text_rgb(0, 0, "─" * fill_w, fg=rule_fg)
        col = fill_w
        surface.draw_text_rgb(0, col, " ", fg=rule_fg)
        col += 1
        surface.draw_text_rgb(
            0,
            col,
            label,
            fg=theme.fg_panel_title,
            style_flags=palette.STYLE_BOLD,
        )
        col += wcswidth(label)
        if status:
            surface.draw_text_rgb(
                0,
                col,
                status,
                fg=theme.fg_danger,
                style_flags=palette.STYLE_BOLD,
            )
            col += wcswidth(status)
        surface.draw_text_rgb(0, col, f" {_TAIL}", fg=rule_fg)
