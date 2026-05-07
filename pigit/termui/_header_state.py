# -*- coding: utf-8 -*-
"""
Module: pigit/termui/_header_state.py
Description: Header semantic state separated from rendering logic.
Author: Zev
Date: 2026-05-07
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable, Optional

from ._segment import Segment
from . import palette

if TYPE_CHECKING:
    from ._component_widgets import Header


class HeaderState:
    """Encapsulates header display state and segment generation."""

    def __init__(self, theme) -> None:
        self.repo: str = ""
        self.branch: str = ""
        self.ahead: int = 0
        self.behind: int = 0
        self.mode: str = ""
        self.merge_target: str = ""
        self.tab: str = ""
        self.tab_key: str = ""
        self._theme = theme

    def apply_to(
        self,
        header: "Header",
        get_badge_fn: Callable[
            [],
            tuple[
                Optional[str],
                Optional[tuple[int, int, int]],
                Optional[tuple[int, int, int]],
            ],
        ],
    ) -> None:
        """Generate segments from current state and push to header."""
        badge, badge_bg, badge_fg = get_badge_fn()

        left: list[Segment] = []
        if badge:
            left.append(
                Segment(
                    f"{badge} ",
                    fg=badge_fg or self._theme.fg_primary,
                    style_flags=palette.STYLE_BOLD,
                )
            )
        left.extend(
            [
                Segment(self.repo, fg=self._theme.fg_primary),
                Segment("  ", fg=self._theme.fg_dim),
                Segment(self.branch, fg=self._theme.accent_cyan),
            ]
        )

        center: list[Segment] = []
        if self.ahead > 0:
            center.append(Segment(f"↑{self.ahead} ", fg=self._theme.accent_green))
        if self.behind > 0:
            center.append(Segment(f"↓{self.behind}", fg=self._theme.accent_yellow))

        right: list[Segment] = []
        if self.merge_target:
            right.append(
                Segment(
                    f"[MERGE] {self.merge_target}  ",
                    fg=self._theme.accent_red,
                    style_flags=palette.STYLE_BOLD,
                )
            )
        if self.mode:
            right.append(
                Segment(
                    f"[{self.mode}]  ",
                    fg=self._theme.fg_primary,
                    style_flags=palette.STYLE_BOLD,
                )
            )
        right.append(
            Segment(
                self.tab,
                fg=self._theme.fg_muted,
                style_flags=palette.STYLE_BOLD,
            )
        )
        if self.tab_key:
            right.append(
                Segment(
                    f" [{self.tab_key}]",
                    fg=self._theme.fg_primary,
                    style_flags=palette.STYLE_BOLD,
                )
            )

        header.set_left(left)
        header.set_center(center)
        header.set_right(right)
