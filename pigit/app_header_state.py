"""
Module: pigit/app_header_state.py
Description: Reactive header display state with Signal-backed properties.
Author: Zev
Date: 2026-05-07
"""

from __future__ import annotations

from typing import Any

from pigit.termui import get_badge, get_badge_signal, palette, Segment
from pigit.termui.reactive import Computed, Signal


class _SignalProp:
    """Descriptor that delegates attribute access to a backing Signal."""

    def __set_name__(self, owner, name):
        self._attr = f"_{name}"

    def __get__(self, obj, objtype=None) -> Any:
        if obj is None:
            return self
        return getattr(obj, self._attr).value

    def __set__(self, obj, value):
        getattr(obj, self._attr).set(value)


class HeaderState:
    """Reactive header display state.

    All fields are backed by Signal. External code reads/writes via
    properties (looks like normal attributes). Derived segments are Computed.
    """

    def __init__(self, theme) -> None:
        self._theme = theme

        # Raw signals
        self._repo = Signal("")
        self._branch = Signal("")
        self._ahead = Signal(0)
        self._behind = Signal(0)
        self._mode = Signal("")
        self._merge_target = Signal("")
        self._tab = Signal("")
        self._tab_key = Signal("")

        # Derived: segment groups (auto-recalculate)
        self._badge_signal = get_badge_signal()
        self._left = Computed(
            self._make_left, deps=[self._repo, self._branch, self._badge_signal]
        )
        self._center = Computed(self._make_center, deps=[self._ahead, self._behind])
        self._right = Computed(
            self._make_right,
            deps=[self._merge_target, self._mode, self._tab, self._tab_key],
        )

    # Signal-backed fields (read/write like normal attributes)
    repo = _SignalProp()
    branch = _SignalProp()
    ahead = _SignalProp()
    behind = _SignalProp()
    mode = _SignalProp()
    merge_target = _SignalProp()
    tab = _SignalProp()
    tab_key = _SignalProp()

    # --- Derived properties (return Computed for reactive binding) ---

    @property
    def left(self) -> Computed[list[Segment]]:
        return self._left

    @property
    def center(self) -> Computed[list[Segment]]:
        return self._center

    @property
    def right(self) -> Computed[list[Segment]]:
        return self._right

    # --- Internal: segment generators ---

    def _make_left(self) -> list[Segment]:
        segs: list[Segment] = []
        badge, _badge_bg, badge_fg = get_badge()
        if badge:
            segs.append(
                Segment(
                    f"{badge} ",
                    fg=badge_fg or self._theme.fg_primary,
                    style_flags=palette.STYLE_BOLD,
                )
            )
        segs.extend(
            [
                Segment(self.repo, fg=self._theme.fg_primary),
                Segment("  ", fg=self._theme.fg_dim),
                Segment(self.branch, fg=self._theme.fg_branch_name),
            ]
        )
        return segs

    def _make_center(self) -> list[Segment]:
        segs: list[Segment] = []
        if self.ahead > 0:
            segs.append(Segment(f"↑{self.ahead} ", fg=self._theme.fg_success))
        if self.behind > 0:
            segs.append(Segment(f"↓{self.behind}", fg=self._theme.fg_warning))
        return segs

    def _make_right(self) -> list[Segment]:
        segs: list[Segment] = []
        if self.merge_target:
            segs.append(
                Segment(
                    f"[MERGE] {self.merge_target}  ",
                    fg=self._theme.fg_danger,
                    style_flags=palette.STYLE_BOLD,
                )
            )
        if self.mode:
            segs.append(
                Segment(
                    f"[{self.mode}]  ",
                    fg=self._theme.fg_primary,
                    style_flags=palette.STYLE_BOLD,
                )
            )
        segs.append(
            Segment(
                self.tab,
                fg=self._theme.fg_muted,
                style_flags=palette.STYLE_BOLD,
            )
        )
        if self.tab_key:
            segs.append(
                Segment(
                    f" [{self.tab_key}]",
                    fg=self._theme.fg_primary,
                    style_flags=palette.STYLE_BOLD,
                )
            )
        return segs

    @property
    def branch_signal(self) -> Signal[str]:
        """Expose the underlying branch signal for external writers."""
        return self._branch
