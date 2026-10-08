# -*- coding: utf-8 -*-
"""
Module: tests/app/test_row_slots.py
Description: Shared row-prefix lanes and the panels' cursor marker.
Author: Zev
Date: 2026-10-07
"""

from __future__ import annotations

from unittest.mock import Mock

from pigit.app_branch import BranchPanel
from pigit.app_commit import CommitPanel
from pigit.app_log_ref import LogRefSheet
from pigit.app_rebase import RebasePanel
from pigit.app_recent_actions import RecentActionsPanel
from pigit.app_row_slots import (
    SLOT_ICON_W,
    SLOT_STATUS_W,
    icon_lane,
    status_lane,
)
from pigit.app_stash import StashPanel
from pigit.app_status import StatusPanel
from pigit.app_theme import THEME
from pigit.git.model import Branch, Commit, File, Stash
from pigit.termui import Segment
from pigit.termui.reactive import Signal
from pigit.termui.wcwidth_table import wcswidth
from pigit.termui.widgets import ACCENT_BAR
from pigit.viewmodels.branch import IBranchViewModel
from pigit.viewmodels.commit import ICommitViewModel
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


def _branch_panel(branches: list[Branch]) -> BranchPanel:
    vm = Mock(spec=IBranchViewModel)
    vm.items = Signal(branches)
    vm.load_error = Signal(None)
    panel = BranchPanel(vm=vm, get_git=lambda: Mock())
    panel.branches = branches
    panel._recompute_meta_width()  # the app does this in _on_items_changed
    panel.content = [b.name for b in branches]
    return panel


def _stash(msg: str, ref: str = "stash@{0}") -> Stash:
    return Stash(ref=ref, sha="a1b2c3d4", msg=msg, when=1700000000)


def _stash_panel(stashes: list[Stash]) -> StashPanel:
    vm = Mock(spec=IStatusViewModel)
    vm.load_stashes.return_value = stashes
    panel = StashPanel(vm=vm)
    panel._load_stashes()
    return panel


def _commit(sha: str = "98085a19dd3c", refs: str = "") -> Commit:
    return Commit(
        sha=sha,
        msg="perf(engine): memoise parse results",
        author="Zev",
        unix_timestamp=1700000000,
        status="pushed",
        extra_info=refs,
        tag=[],
    )


def _commit_panel(commits: list[Commit]) -> CommitPanel:
    vm = Mock(spec=ICommitViewModel)
    vm.items = Signal([])
    vm.load_error = Signal(None)
    vm.graph_rows = []
    vm.remotes = ()
    panel = CommitPanel(vm=vm)
    panel.commits = commits
    panel._rebuild_rows()
    return panel


def _status_panel(files: list[File], *, tree: bool) -> StatusPanel:
    vm = Mock(spec=IStatusViewModel)
    vm.items = Signal(files)
    vm.load_error = Signal(None)
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
        panel = _status_panel([_file("src/中文模块.py"), _file("README.md")], tree=True)
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


class TestMetadataBlocksShareOneLeftEdge:
    """A right-anchored block sits at ``w - block_width``, so rows whose
    metadata differs in width would start theirs at different columns and the
    date would shift under each other. Padding every row's block to the
    panel's widest pins them."""

    def test_branch_rows_with_and_without_tracking_agree(self):
        # Both must carry metadata: a row with none has nothing to align.
        panel = _branch_panel(
            [
                Branch(
                    "dev",
                    "2",
                    "1",
                    True,
                    upstream_name="origin/dev",
                    committed_at=1700000000,
                ),
                Branch("feature", "?", "?", False, committed_at=1700000000),
            ]
        )
        widths = {_width(panel.describe_row(idx, False)[2]) for idx in range(2)}
        assert widths == {panel._max_right_w}

    def test_stash_rows_agree(self):
        # Different ref widths, or the padding would be a no-op and the
        # assertion would hold with the alignment removed.
        panel = _stash_panel([_stash("wip one"), _stash("wip two", ref="stash@{10}")])
        widths = {_width(panel.describe_row(idx, False)[2]) for idx in range(2)}
        assert widths == {panel._max_right_w}

    def test_the_ref_still_precedes_the_time(self):
        panel = _stash_panel([_stash("stash@{0}")])
        right = panel.describe_row(0, False)[2]
        text = "".join(seg.text for seg in right)
        assert text.strip().startswith("stash@{0}")
        assert text.rstrip().endswith("ago")


class TestCommitSubjectColumn:
    """The subject is the only column in a message list worth scanning, and it
    used to move with the width of that row's refs."""

    @staticmethod
    def _starts(panel: CommitPanel) -> list[int]:
        return [
            _width(panel.describe_row(idx, False)[0])
            for idx in range(len(panel.commits))
        ]

    def test_the_subject_starts_at_the_same_column_with_or_without_refs(self):
        panel = _commit_panel(
            [_commit(refs=" (HEAD -> main, tag: v0.4.0)"), _commit(refs="")]
        )
        assert len(set(self._starts(panel))) == 1

    def test_refs_trail_the_subject(self):
        panel = _commit_panel([_commit(refs=" (HEAD -> main)")])
        _left, main, _right = panel.describe_row(0, False)
        text = "".join(seg.text for seg in main)
        assert text.index("memoise") < text.index("(HEAD")

    def test_refs_keep_the_cursor_rows_background(self):
        """The selected-row fill is painted from the segments, so refs that do
        not carry it leave a gap in the middle of the highlighted row."""
        panel = _commit_panel([_commit(refs=" (HEAD -> main)")])
        _left, main, _right = panel.describe_row(0, True)
        subject_bg = main[0].bg
        refs = [seg for seg in main if "HEAD" in seg.text]
        assert refs
        assert all(seg.bg == subject_bg for seg in refs)

    def test_refs_do_not_widen_the_right_block(self):
        """The reason refs stayed in ``main``: ``right`` is dropped wholesale
        once ``left + right + 2`` exceeds the terminal, so widening it with the
        refs would take the author and the date down with them. Measured, that
        moves the drop point from ~27 columns to ~42.

        ``left`` already carries the framework's cursor cell by the time
        ``_draw_row_layout`` sees it, hence the leading 1.
        """
        panel = _commit_panel([_commit(refs=" (HEAD -> main, tag: v0.4.0)")])
        left, main, right = panel.describe_row(0, False)
        subject = "perf(engine): memoise parse results"
        assert _width(main) > len(subject)  # the row really does carry refs
        assert 1 + _width(left) + _width(right) + 2 <= 27


class TestEveryPanelUsesTheBrandCursor:
    """``option_list.py`` declares ``ACCENT_BAR`` the brand marker for the
    cursor column, and ``CURSOR_ACCENT`` makes it degrade to a space when the
    panel is not focused -- which a literal glyph does not, so the column
    keeps its width either way."""

    PANELS = (
        StatusPanel,
        BranchPanel,
        CommitPanel,
        StashPanel,
        LogRefSheet,
        RecentActionsPanel,
        RebasePanel,
    )

    def test_cursor_is_the_accent_bar(self):
        for panel in self.PANELS:
            assert panel.CURSOR == ACCENT_BAR, panel.__name__

    def test_cursor_accent_is_enabled(self):
        for panel in self.PANELS:
            assert panel.CURSOR_ACCENT is True, panel.__name__
