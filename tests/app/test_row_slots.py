# -*- coding: utf-8 -*-
"""
Module: tests/app/test_row_slots.py
Description: Shared row-prefix lanes for the list panels.
Author: Zev
Date: 2026-10-07
"""

from __future__ import annotations

from unittest.mock import Mock

from pigit.app_row_slots import (
    SLOT_ICON_W,
    SLOT_STATUS_W,
    icon_lane,
    status_lane,
)
from pigit.app_status import StatusPanel
from pigit.app_theme import THEME
from pigit.git.model import File
from pigit.termui import Segment
from pigit.termui.reactive import Signal
from pigit.termui.wcwidth_table import wcswidth
from pigit.viewmodels.status import IStatusViewModel

FG = (200, 200, 200)


def _width(segments) -> int:
    return sum(wcswidth(seg.text) for seg in segments)


def _file(name: str, short_status: str = " M") -> File:
    return File(
        name=name,
        display_str=name,
        short_status=short_status,
        has_staged_change=False,
        has_unstaged_change=True,
        tracked=True,
        deleted=False,
        added=False,
        has_merged_conflicts=False,
        has_inline_merged_conflicts=False,
    )


def _status_panel(files: list[File], *, tree: bool) -> StatusPanel:
    vm = Mock(spec=IStatusViewModel)
    vm.items = Signal(files)
    vm.repo_path = "/tmp/repo"
    panel = StatusPanel(
        vm=vm, default_view="tree" if tree else "flat", nerd_icons=False
    )
    panel._all_files = list(files)
    panel._apply_filter()
    return panel


class TestLanes:
    def test_status_lane_pads_to_its_width(self):
        assert _width(status_lane([Segment("M")], pad_fg=FG)) == SLOT_STATUS_W

    def test_icon_lane_pads_to_its_width(self):
        assert _width(icon_lane([Segment("▸")], pad_fg=FG)) == SLOT_ICON_W

    def test_empty_lane_still_occupies_its_width(self):
        """The whole point: an empty lane reserves its cells instead of
        collapsing, which is what keeps the identity column still."""
        assert _width(status_lane([], pad_fg=FG)) == SLOT_STATUS_W
        assert _width(icon_lane([], pad_fg=FG)) == SLOT_ICON_W

    def test_full_lane_is_not_padded(self):
        lane = status_lane([Segment("M"), Segment("A")], pad_fg=FG)
        assert [seg.text for seg in lane] == ["M", "A"]

    def test_content_past_the_lane_width_is_returned_untouched(self):
        """A lane is a minimum to reserve, not a budget to spend."""
        lane = status_lane([Segment("ABC")], pad_fg=FG)
        assert [seg.text for seg in lane] == ["ABC"]

    def test_a_wide_glyph_counts_as_its_display_width(self):
        lane = icon_lane([Segment("修")], pad_fg=FG)
        assert _width(lane) == SLOT_ICON_W


class TestStatusPrefixIsTheSameOnEveryRow:
    """Directory rows and file rows reserve the same prefix width, so the
    identity column does not move between them. Directory rows used to reserve
    one cell against a file row's four, putting the icon -- and the name --
    three columns to the left on every directory row."""

    @staticmethod
    def _left_widths(panel: StatusPanel) -> list[int]:
        return [
            _width(panel.describe_row(idx, False)[0])
            for idx in range(len(panel.content))
        ]

    def test_tree_dir_and_file_rows_share_one_prefix_width(self):
        panel = _status_panel([_file("src/a.py"), _file("README.md")], tree=True)
        widths = self._left_widths(panel)
        assert len(widths) >= 3  # a directory row and two file rows
        assert len(set(widths)) == 1, widths

    def test_flat_rows_share_one_prefix_width(self):
        panel = _status_panel([_file("a.py"), _file("b.py")], tree=False)
        assert len(set(self._left_widths(panel))) == 1

    def test_a_cjk_name_does_not_change_the_prefix_width(self):
        panel = _status_panel(
            [_file("src/中文模块.py"), _file("README.md")], tree=True
        )
        assert len(set(self._left_widths(panel))) == 1

    def test_the_icon_takes_the_names_colour_on_a_selected_row(self):
        """The icon used to share the name's segment and inherit its colours
        from it; as a lane of its own it has to be told explicitly, or a
        multi-selected file gets a plain icon next to a tinted name."""
        panel = _status_panel([_file("a.py")], tree=False)
        panel._selected = {0}
        left, main, _right = panel.describe_row(0, False)
        assert main[0].fg == THEME.fg_staged_renamed
        assert left[3].fg == main[0].fg  # the icon, inside the icon lane
