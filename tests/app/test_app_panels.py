# -*- coding: utf-8 -*-
"""Tests for pigit app panel components."""

from __future__ import annotations

from contextlib import ExitStack

import pytest

from pigit.app_diff import DiffViewer
from pigit.app_theme import THEME
from pigit.termui.component import ComponentError
from pigit.termui.surface import Surface


class TestDiffViewer:
    def test_init(self):
        d = DiffViewer()
        assert d._lines == []
        assert d._heatmap == []
        assert d._heatmap_colors == []
        assert d._line_numbers == []

    def test_set_content_computes_heatmap(self):
        d = DiffViewer()
        d.set_content(["+added line", "-removed line", "@@ context", " context"])
        assert len(d._heatmap) == 4
        assert len(d._heatmap_colors) == 4
        # Added line gets green symbol
        assert d._heatmap[0] in {"░", "▒", "▓", "█"}
        # Removed line gets red symbol
        assert d._heatmap[1] in {"░", "▒", "▓", "█"}
        # Context lines get space
        assert d._heatmap[2] == " "
        assert d._heatmap[3] == " "

    def testpaint_empty(self):
        d = DiffViewer()
        s = Surface(10, 5)
        d.paint(s)
        # No crash, no content

    def testpaint_diff(self):
        d = DiffViewer()
        d.set_content(["+added", "-removed", " context"])
        d.resize((20, 5))
        s = Surface(20, 5)
        d.paint(s)
        # With box border: row 0 = top border, row 1+ = content, last row = bottom border
        lines = s.lines()
        assert "\u250c" in lines[0]  # ┌ top-left corner
        assert "\u2510" in lines[0]  # ┐ top-right corner
        assert "0" in lines[1]
        assert "+added" in lines[1]
        assert "\u2514" in lines[-1]  # └ bottom-left corner
        assert "\u2518" in lines[-1]  # ┘ bottom-right corner

    def testpaint_borderless_fallback(self):
        """When surface is too small for borders, fall back to borderless."""
        d = DiffViewer()
        d.set_content(["+added"])
        d.resize((10, 2))
        s = Surface(10, 2)
        d.paint(s)
        lines = s.lines()
        # Should render without box border characters
        assert "\u250c" not in lines[0]
        # Borderless renders line number + truncated content + heatmap
        assert "+ad" in lines[0] or "added" in lines[0]

    def test_hunk_header_scrolls_with_col_offset(self):
        """@@ headers follow horizontal scroll instead of staying fixed."""
        d = DiffViewer()
        d.set_content(["@@ -1,20 +1,20 @@", "+added", " context"])
        d.resize((30, 5))
        d._col_offset = 6
        s = Surface(30, 5)
        d.paint(s)
        row = "".join(c.char for c in s.rows()[1])
        # The marker reserves column 6, so the header is scrolled by 7 rather
        # than by the raw offset of 6: past "@@ -1,2" instead of "@@ -1,".
        assert row[6] == "\u2039"
        assert "0 +1,20 @@" in row
        # NOT pinned at the fixed text-start column \u2014 that is the point.
        assert "@@ -1,20 +1,20 @@" not in row
        assert row[0] == "\u2502"  # border intact, nothing overwrites it

    def test_hunk_header_uses_accent_tone(self):
        """@@ hunk headers render on the derived hunk tone with hunk fg."""
        d = DiffViewer()
        d.set_content(["@@ -1,3 +1,4 @@", "+added", " context"])
        d.resize((40, 5))
        s = Surface(40, 5)
        d.paint(s)
        row = s.rows()[1]
        # Column 6 = 1 (border) + 4 (gutter) + 1 (prefix)
        cell = row[6]
        assert cell.bg == THEME.bg_diff_hunk
        assert cell.fg == THEME.fg_diff_hunk

    def test_line_numbers_flush_against_prefix(self):
        """Gutter width matches formatting so numbers sit flush before +/-."""
        d = DiffViewer()
        d.set_content(["+added", "-removed"])
        d.resize((20, 4))
        s = Surface(20, 4)
        d.paint(s)
        row = s.rows()[1]
        # gutter ends at col 5 (1 border + 4 gutter), +/- prefix follows
        assert row[5].char == "+"

    def test_line_numbers_hidden_on_narrow_surface(self):
        """Narrow surfaces drop the line-number gutter entirely."""
        d = DiffViewer()
        d.set_content(["+added"])
        d.resize((14, 3))
        s = Surface(14, 3)
        d.paint(s)
        row = s.rows()[1]
        # text starts right after the border; no gutter columns
        assert row[1].char == "+"

    def test_scroll_budget_matches_adaptive_gutter(self):
        """max_col_offset must use the adaptive gutter width (0 on narrow
        panels) or the scroll range overshoots by the hidden gutter."""
        d = DiffViewer()
        d.set_content(["+" + "x" * 60])
        d.resize((14, 5))  # < 16 cols: gutter hidden
        d._compute_max_col_offset(content_w=12)
        # main_w = 12 - 0(gutter) - 1(prefix) - 1 = 10; max_text_w = 60
        assert d._max_col_offset == 50

        d2 = DiffViewer()
        d2.set_content(["+" + "x" * 60])
        d2.resize((40, 5))
        d2._compute_max_col_offset(content_w=38)
        # main_w = 38 - 4(gutter) - 1(prefix) - 1 = 32; max_text_w = 60
        assert d2._max_col_offset == 28

    def test_hunk_navigation(self):
        d = DiffViewer()
        d.set_content(["@@ hunk1", "+line1", "@@ hunk2", "+line2"])
        d.scroll_i = 0
        d._next_hunk()
        assert d.scroll_i == 2  # jumped to second hunk
        d._prev_hunk()
        assert d.scroll_i == 0  # jumped back to first hunk

    def test_scroll_position_cache(self):
        from pigit.termui.component import Component

        class FakeSource(Component):
            def paint(self, surface):
                pass

        source = FakeSource()
        d = DiffViewer()
        d.scroll_i = 5
        from pigit.termui.types import EventType, EVT_GOTO

        d.update(EVT_GOTO, source=source, key="test.py", content=["line1"])
        assert d.i_cache_key == "test.py"
        assert d.come_from is source

    def test_leave_display_no_parent(self):
        from pigit.termui.component import Component

        class FakeSource(Component):
            def paint(self, surface):
                pass

        d = DiffViewer()
        d.come_from = FakeSource()
        # emit without parent logs a warning instead of raising
        d._leave_display()

    def test_leave_display_with_parent(self):
        from pigit.termui.component import Component

        class FakeParent(Component):
            def __init__(self):
                self._received = []
                super().__init__()

            def _handle_event(self, key):
                pass

            def paint(self, surface):
                pass

            def on_event(self, action, **data):
                self._received.append((action, data))
                return True

        class FakeSource(Component):
            def paint(self, surface):
                pass

        parent = FakeParent()
        d = DiffViewer()
        d.parent = parent
        source = FakeSource()
        d.come_from = source
        d._leave_display()
        assert len(parent._received) == 1
        assert parent._received[0][0].name == "goto"
        assert parent._received[0][1]["target"] is source

    # -- Wide-character regression tests --

    def testpaint_wide_char_no_overflow(self):
        """Regression: CJK diff content must not overflow and overwrite borders."""
        d = DiffViewer()
        d.set_content(["+中文内容测试"])
        d.resize((20, 5))
        s = Surface(20, 5)
        d.paint(s)
        lines = s.lines()
        rows = s.rows()
        # Box borders must remain intact
        assert lines[0][0] == "\u250c"  # ┌ top-left
        assert lines[0][-1] == "\u2510"  # ┐ top-right
        assert lines[-1][0] == "\u2514"  # └ bottom-left
        assert lines[-1][-1] == "\u2518"  # ┘ bottom-right
        # Content row must have left/right borders intact
        assert rows[1][0].char == "\u2502"  # │ left border
        assert rows[1][-1].char == "\u2502"  # │ right border

    def testpaint_wide_char_heatmap_intact(self):
        """Heatmap symbol must not be overwritten by wide-char diff text."""
        d = DiffViewer()
        d.set_content(["+中文内容测试"])
        d.resize((20, 5))
        s = Surface(20, 5)
        d.paint(s)
        # Heatmap is at column w-2 on content rows
        heatmap_col = 18
        for r in range(1, 4):
            cell = s.rows()[r][heatmap_col]
            # Should be a heatmap symbol (not space, not part of diff text)
            assert cell.char in {"\u2591", "\u2592", "\u2593", "\u2588", " "}

    def testpaint_borderless_wide_char(self):
        """Borderless fallback must also handle wide chars without overflow."""
        d = DiffViewer()
        d.set_content(["+中文内容测试"])
        # w=7 triggers borderless fallback (w <= LINE_NO_WIDTH + 3 = 7)
        d.resize((7, 3))
        s = Surface(7, 3)
        d.paint(s)
        lines = s.lines()
        # Should not have box borders (too small)
        assert "\u250c" not in lines[0]
        # Each row must have exactly surface.width cells
        for row in s.rows():
            assert len(row) == 7
        # Rightmost column should be heatmap symbol (not overwritten)
        cell = s.rows()[0][-1]
        assert cell.char in {"\u2591", "\u2592", "\u2593", "\u2588", " "}

    def testpaint_multiple_wide_chars(self):
        """Multiple CJK chars in a row should all render within bounds."""
        d = DiffViewer()
        d.set_content(["+中文内容测试", "-更多中文测试"])
        d.resize((25, 6))
        s = Surface(25, 6)
        d.paint(s)
        lines = s.lines()
        rows = s.rows()
        # Every row must have exactly surface.width cells
        for row in rows:
            assert len(row) == 25
        # Borders intact
        assert rows[0][0].char == "\u250c"
        assert rows[0][-1].char == "\u2510"
        assert rows[-1][0].char == "\u2514"
        assert rows[-1][-1].char == "\u2518"

    def test_set_content_expands_tabs(self):
        """Tab characters must be expanded to spaces to prevent width mismatch."""
        d = DiffViewer()
        d.set_content(["+\t\tName"])
        # After expandtabs(8): '+' at col 0, first tab -> 7 spaces to col 8,
        # second tab -> 8 spaces to col 16, then "Name"
        assert "\t" not in d._lines[0]
        assert d._lines[0] == "+               Name"

    def testpaint_with_tabs_no_overflow(self):
        """Regression: tab-heavy diff lines must not overflow surface bounds."""
        d = DiffViewer()
        d.set_content(["+\t\tPotentialRange string"])
        d.resize((40, 5))
        s = Surface(40, 5)
        d.paint(s)
        lines = s.lines()
        # Top and bottom borders must be intact
        assert lines[0][0] == "\u250c"
        assert lines[0][-1] == "\u2510"
        assert lines[-1][0] == "\u2514"
        assert lines[-1][-1] == "\u2518"
        # No tab characters should remain in rendered output
        assert "\t" not in lines[1]
        # Right border on content row must be │
        assert s.rows()[1][-1].char == "\u2502"

    def test_update_expands_tabs(self):
        """update() with list content must also expand tabs via set_content."""
        from pigit.termui.component import Component
        from pigit.termui.types import EventType, EVT_GOTO

        class FakeSource(Component):
            def paint(self, surface):
                pass

        d = DiffViewer()
        d.parent = FakeSource()
        d.update(
            EVT_GOTO,
            source=FakeSource(),
            key="test.go",
            content=["+\t\tName"],
        )
        assert "\t" not in d._lines[0]
        assert d._lines[0] == "+               Name"

    def testpaint_blank_rows_have_borders(self):
        """When content is shorter than viewport, blank rows must keep borders."""
        d = DiffViewer()
        d.set_content(["+line1", "-line2"])
        d.resize((20, 8))
        s = Surface(20, 8)
        d.paint(s)
        rows = s.rows()
        # Row 0: top border
        assert rows[0][0].char == "\u250c"
        # Row 1-2: content rows with borders
        assert rows[1][0].char == "\u2502"
        assert rows[1][-1].char == "\u2502"
        assert rows[2][0].char == "\u2502"
        assert rows[2][-1].char == "\u2502"
        # Row 3-6: blank rows must still have left/right borders
        for r in range(3, 7):
            assert rows[r][0].char == "\u2502", f"row {r} missing left border"
            assert rows[r][-1].char == "\u2502", f"row {r} missing right border"
        # Row 7: bottom border
        assert rows[7][0].char == "\u2514"


class TestBranchPanelLifecycle:
    """BranchPanel + ViewModel integration tests."""

    def test_activate_triggers_vm_refresh(self):
        from unittest.mock import Mock
        from pigit.viewmodels.branch import IBranchViewModel
        from pigit.termui.reactive import Signal

        vm = Mock(spec=IBranchViewModel)
        vm.items = Signal([])
        from pigit.app_branch import BranchPanel

        panel = BranchPanel(
            get_git=lambda: Mock(bisect_status=Mock(return_value=None)), vm=vm
        )
        panel.mount()
        vm.refresh.assert_called_once()

    def test_unmount_does_not_dispose_vm(self):
        """Session owns VM lifetime; panel unmount only drops signal bindings."""
        from unittest.mock import Mock
        from pigit.viewmodels.branch import IBranchViewModel
        from pigit.termui.reactive import Signal

        vm = Mock(spec=IBranchViewModel)
        vm.items = Signal([])
        from pigit.app_branch import BranchPanel

        panel = BranchPanel(
            get_git=lambda: Mock(bisect_status=Mock(return_value=None)), vm=vm
        )
        panel.mount()
        panel.unmount()
        vm.dispose.assert_not_called()

    def test_set_vm_rebinds_items_and_does_not_dispose(self):
        """set_vm drops old subscriptions, binds the new VM, and reloads."""
        from unittest.mock import Mock
        from pigit.git.model import Branch
        from pigit.viewmodels.branch import IBranchViewModel
        from pigit.termui.reactive import Signal
        from pigit.app_branch import BranchPanel

        old_vm = Mock(spec=IBranchViewModel)
        old_vm.items = Signal([])
        new_vm = Mock(spec=IBranchViewModel)
        new_vm.items = Signal([])

        panel = BranchPanel(
            get_git=lambda: Mock(bisect_status=Mock(return_value=None)), vm=old_vm
        )
        panel.mount()
        old_vm.refresh.reset_mock()

        panel.set_vm(new_vm)
        new_vm.refresh.assert_called_once()
        old_vm.dispose.assert_not_called()
        new_vm.dispose.assert_not_called()

        old_vm.items.set([Branch("stale", "0", "0", False)])
        assert panel.branches == []

        new_vm.items.set([Branch("fresh", "0", "0", True)])
        assert [b.name for b in panel.branches] == ["fresh"]

    def test_set_vm_unmounted_swaps_pointer_and_binds_on_mount(self):
        """set_vm before mount only swaps the pointer; mount binds + refreshes."""
        from unittest.mock import Mock
        from pigit.viewmodels.branch import IBranchViewModel
        from pigit.termui.reactive import Signal
        from pigit.app_branch import BranchPanel

        old_vm = Mock(spec=IBranchViewModel)
        old_vm.items = Signal([])
        new_vm = Mock(spec=IBranchViewModel)
        new_vm.items = Signal([])

        panel = BranchPanel(
            get_git=lambda: Mock(bisect_status=Mock(return_value=None)), vm=old_vm
        )  # not mounted
        panel.set_vm(new_vm)
        assert panel._vm is new_vm
        new_vm.refresh.assert_not_called()

        panel.mount()
        new_vm.refresh.assert_called_once()
        assert len(panel._vm_unsubs) == 1

    def test_items_changed_updates_content(self):
        from unittest.mock import Mock
        from pigit.git.model import Branch
        from pigit.viewmodels.branch import IBranchViewModel
        from pigit.termui.reactive import Signal

        vm = Mock(spec=IBranchViewModel)
        vm.items = Signal([])
        from pigit.app_branch import BranchPanel

        panel = BranchPanel(
            get_git=lambda: Mock(bisect_status=Mock(return_value=None)), vm=vm
        )
        panel.mount()
        vm.items.set([Branch("main", "0", "0", True)])
        assert len(panel.content) == 1
        assert panel.branches[0].name == "main"

    def test_create_pull_request_opens_github_compare(self, monkeypatch):
        from unittest.mock import Mock
        from pigit.git.model import Branch
        from pigit.viewmodels.branch import IBranchViewModel
        from pigit.termui.reactive import Signal
        from pigit.app_branch import BranchPanel

        vm = Mock(spec=IBranchViewModel)
        vm.items = Signal([])
        vm.get_remote_url.return_value = "git@github.com:zlj-zz/pigit.git"
        opened: list[str] = []
        monkeypatch.setattr("webbrowser.open", lambda url: opened.append(url) or True)

        panel = BranchPanel(
            get_git=lambda: Mock(bisect_status=Mock(return_value=None)), vm=vm
        )
        panel.mount()
        vm.items.set([Branch("dev", "0", "0", True)])
        panel.create_pull_request()

        assert opened == ["https://github.com/zlj-zz/pigit/compare/dev?expand=1"]


class TestCommitPanelLifecycle:
    """CommitPanel + ViewModel integration tests."""

    def test_activate_triggers_vm_refresh(self):
        from unittest.mock import Mock
        from pigit.viewmodels.commit import ICommitViewModel
        from pigit.termui.reactive import Signal

        vm = Mock(spec=ICommitViewModel)
        vm.items = Signal([])
        from pigit.app_commit import CommitPanel

        panel = CommitPanel(vm=vm)
        panel.mount()
        vm.refresh.assert_called_once()

    def test_unmount_does_not_dispose_vm(self):
        """Session owns VM lifetime; panel unmount only drops signal bindings."""
        from unittest.mock import Mock
        from pigit.viewmodels.commit import ICommitViewModel
        from pigit.termui.reactive import Signal

        vm = Mock(spec=ICommitViewModel)
        vm.items = Signal([])
        from pigit.app_commit import CommitPanel

        panel = CommitPanel(vm=vm)
        panel.mount()
        panel.unmount()
        vm.dispose.assert_not_called()

    def test_set_vm_rebinds_items_and_does_not_dispose(self):
        """set_vm drops old subscriptions, binds the new VM, and reloads."""
        from unittest.mock import Mock
        from pigit.git.model import Commit
        from pigit.viewmodels.commit import ICommitViewModel
        from pigit.termui.reactive import Signal
        from pigit.app_commit import CommitPanel

        old_vm = Mock(spec=ICommitViewModel)
        old_vm.items = Signal([])
        old_vm.graph_rows = []
        new_vm = Mock(spec=ICommitViewModel)
        new_vm.items = Signal([])
        new_vm.graph_rows = []

        panel = CommitPanel(vm=old_vm)
        panel.mount()
        old_vm.refresh.reset_mock()

        panel.set_vm(new_vm)
        new_vm.refresh.assert_called_once()
        old_vm.dispose.assert_not_called()
        new_vm.dispose.assert_not_called()

        # Old signal must no longer drive the panel; the new one must.
        old_vm.items.set([Commit("stale", "old", "Zev", 0, "pushed", "", [])])
        assert panel.commits == []

        new_vm.items.set([Commit("fresh", "new", "Zev", 0, "pushed", "", [])])
        assert [c.sha for c in panel.commits] == ["fresh"]
        assert len(panel._vm_unsubs) == 1

    def test_items_changed_rebuilds_content(self):
        from unittest.mock import Mock
        from pigit.git.model import Commit
        from pigit.viewmodels.commit import ICommitViewModel
        from pigit.termui.reactive import Signal

        vm = Mock(spec=ICommitViewModel)
        vm.items = Signal([])
        vm.graph_rows = []
        vm.remotes = ()
        from pigit.app_commit import CommitPanel

        panel = CommitPanel(vm=vm)
        panel.mount()
        vm.items.set([Commit("abc1234", "msg", "Zev", 0, "pushed", "", [])])
        assert len(panel.commits) == 1
        assert panel.commits[0].sha == "abc1234"

    def test_items_refresh_drops_stale_head_decoration(self):
        """Refs cache must invalidate before row rebuild, not after.

        After a new tip commit, the previous tip keeps its sha; a leftover
        ``_refs_cache`` entry would bake ``HEAD -> branch`` into the row cache.
        """
        from unittest.mock import Mock
        from pigit.git.model import Commit
        from pigit.viewmodels.commit import ICommitViewModel
        from pigit.termui.reactive import Signal
        from pigit.app_commit import CommitPanel

        vm = Mock(spec=ICommitViewModel)
        vm.items = Signal([])
        vm.graph_rows = []
        vm.remotes = ()
        panel = CommitPanel(vm=vm)
        panel.mount()

        old_tip = Commit(
            "7ae8c9792406ac728a9",
            "old tip",
            "Zev",
            1,
            "unpushed",
            "(HEAD -> dev)",
            [],
        )
        vm.items.set([old_tip])
        # Simulate a render that re-seeds refs_cache after items-changed cleared it.
        panel._ref_segments(old_tip, cursor_flags=0)

        new_tip = Commit(
            "4a3ad3bbec2801cbee7",
            "new tip",
            "Zev",
            2,
            "unpushed",
            "(HEAD -> dev)",
            [],
            ["7ae8c9792406ac728a9"],
        )
        former_tip = Commit(
            "7ae8c9792406ac728a9",
            "old tip",
            "Zev",
            1,
            "unpushed",
            "",
            [],
        )
        vm.items.set([new_tip, former_tip])

        def _main_text(row_idx: int) -> str:
            _left, main = panel._row_cache[row_idx]
            return "".join(seg.text for seg in main)

        assert "HEAD" in _main_text(0)
        assert "HEAD" not in _main_text(1)


class TestStatusPanelLifecycle:
    def test_set_vm_rebinds_items_and_does_not_dispose(self):
        """Status set_vm drops old subscriptions, sets loading, reloads.

        Status is the trickiest retarget: it shares ``status_vm`` with Stash,
        sets a loading skeleton, and carries search-filter state.
        """
        from unittest.mock import Mock
        from pigit.git.model import File
        from pigit.viewmodels.status import IStatusViewModel
        from pigit.termui.reactive import Signal
        from pigit.app_status import StatusPanel

        old_vm = Mock(spec=IStatusViewModel)
        old_vm.items = Signal([])
        new_vm = Mock(spec=IStatusViewModel)
        new_vm.items = Signal([])

        panel = StatusPanel(vm=old_vm, default_view="flat")
        panel.mount()
        old_vm.refresh.reset_mock()

        panel.set_vm(new_vm)
        new_vm.refresh.assert_called_once()
        assert panel.loading is True
        old_vm.dispose.assert_not_called()
        new_vm.dispose.assert_not_called()

        # Old signal must no longer drive the panel; the new one must.
        old_vm.items.set(
            [
                File(
                    "stale.py",
                    "stale.py",
                    " M",
                    False,
                    True,
                    True,
                    True,
                    False,
                    False,
                    False,
                )
            ]
        )
        assert panel.files == []

        new_vm.items.set(
            [
                File(
                    "fresh.py",
                    "fresh.py",
                    " M",
                    False,
                    True,
                    True,
                    True,
                    False,
                    False,
                    False,
                )
            ]
        )
        assert [f.name for f in panel.files] == ["fresh.py"]


def _commits_on_day(days_ago: int, count: int) -> list:
    """*count* commits sharing one day, ``days_ago`` days back."""
    import datetime

    from pigit.git.model import Commit

    stamp = datetime.datetime.now() - datetime.timedelta(days=days_ago, hours=1)
    ts = int(stamp.timestamp())
    return [
        Commit(f"{days_ago:04x}{i:04x}", f"msg {i}", "Zev", ts, "pushed", "", [])
        for i in range(count)
    ]


class TestContributionPanel:
    """The Graph tab: a board of blocks fed by the commit item signal."""

    def _panel(self, commits=None):
        from unittest.mock import Mock

        from pigit.app_graph_panel import ContributionPanel
        from pigit.termui.reactive import Signal
        from pigit.viewmodels.commit import ICommitViewModel

        vm = Mock(spec=ICommitViewModel)
        vm.items = Signal(commits or [])
        panel = ContributionPanel(vm=vm)
        panel.mount()
        return vm, panel

    def test_replaced_list_rebuilds_instead_of_appending(self):
        """A longer list of new commits is a re-pin, not a streamed batch.

        Only length is compared by the naive rule, so re-pinning to a longer
        ref would count the old ref's commits and then top up with the new
        ref's tail — inflating the peak day.
        """
        vm, panel = self._panel()
        vm.items.set(_commits_on_day(0, 3))
        assert sum(panel._heatmap._day_counts.values()) == 3

        vm.items.set(_commits_on_day(1, 5))
        assert panel._heatmap._max_count == 5
        assert sum(panel._heatmap._day_counts.values()) == 5

    def test_streamed_batch_appends_without_rebuilding(self):
        """Every block sees the same decision, and none recounts everything."""
        from unittest.mock import patch

        def counting(block, counter, key):
            """Wrap one method so the call is counted as well as run."""
            original = getattr(block, key)

            def wrapper(*args, **kwargs):
                counter[key] += 1
                return original(*args, **kwargs)

            return patch.object(block, key, wrapper)

        vm, panel = self._panel()
        counters = [{name: 0 for name in ("set_commits", "add_commits")}
                    for _ in panel._blocks]
        with ExitStack() as stack:
            for block, counter in zip(panel._blocks, counters, strict=True):
                for name in ("set_commits", "add_commits"):
                    stack.enter_context(counting(block, counter, name))

            first = _commits_on_day(0, 3)
            vm.items.set(first)
            assert [c["set_commits"] for c in counters] == [1] * len(panel._blocks)
            assert [c["add_commits"] for c in counters] == [0] * len(panel._blocks)

            vm.items.set([*first, *_commits_on_day(1, 2)])
            assert [c["set_commits"] for c in counters] == [1] * len(panel._blocks), (
                "an extension must not rebuild"
            )
            assert [c["add_commits"] for c in counters] == [1] * len(panel._blocks)

        assert sum(panel._heatmap._day_counts.values()) == 5
        assert sum(panel._chart._chart._series["Zev"]) == 5
        assert sum(panel._punch_card._hour_counts.values()) == 5

    def test_mount_replays_items_loaded_before_mount(self):
        from unittest.mock import Mock

        from pigit.app_graph_panel import ContributionPanel
        from pigit.termui.reactive import Signal
        from pigit.viewmodels.commit import ICommitViewModel

        vm = Mock(spec=ICommitViewModel)
        vm.items = Signal(_commits_on_day(0, 2))
        panel = ContributionPanel(vm=vm)
        panel.mount()
        assert sum(panel._heatmap._day_counts.values()) == 2
        assert panel._chart._chart._series

    def test_set_vm_drops_the_previous_repo_counts(self):
        from unittest.mock import Mock

        from pigit.termui.reactive import Signal
        from pigit.viewmodels.commit import ICommitViewModel

        vm, panel = self._panel()
        vm.items.set(_commits_on_day(0, 4))
        assert sum(panel._heatmap._day_counts.values()) == 4

        other = Mock(spec=ICommitViewModel)
        other.items = Signal(_commits_on_day(1, 1))
        panel.set_vm(other)
        assert sum(panel._heatmap._day_counts.values()) == 1

    def test_mouse_wheel_pans_the_board(self):
        from pigit.termui import MouseButton, MouseKind

        class _Event:
            kind = MouseKind.PRESS
            button = MouseButton.WHEEL_RIGHT

        _, panel = self._panel()
        panel.resize((40, 10))
        assert panel._board.content_size[0] > 40, "nothing to pan otherwise"

        assert panel.handle_mouse(_Event()) is True
        assert panel._board.pan[1] > 0  # pan is (rows, cols)

    def test_the_banner_takes_its_rows_off_the_top(self):
        """The wordmark is fixed panel chrome, so the board gets the rest."""
        from pigit.app_graph_panel import _BANNER_H

        _, panel = self._panel()
        panel.resize((100, 30))
        assert panel._board.viewport_size == (100, 30 - _BANNER_H)

    def test_the_banner_does_not_pan_with_the_board(self):
        """It is part of the panel, not a block on the canvas."""
        from pigit.app_graph_panel import _BANNER, _BANNER_H, _BANNER_PAD_LEFT

        _, panel = self._panel()
        panel.resize((120, 30))

        def banner_rows() -> list[str]:
            surface = Surface(120, 30)
            panel.paint(surface)
            return ["".join(cell.char for cell in row) for row in surface._rows[:5]]

        before = banner_rows()
        pad = " " * _BANNER_PAD_LEFT
        assert before[0].rstrip() == pad + _BANNER[0]
        assert before[_BANNER_H - 1].rstrip() == pad + _BANNER[-1]
        assert before[1][_BANNER_PAD_LEFT] == "/", "the mark is inset from the edge"

        panel._board.pan_by(rows=5, cols=5)
        assert banner_rows() == before

    def test_a_narrow_panel_clips_the_banner_rather_than_wrapping_it(self):
        _, panel = self._panel()
        panel.resize((20, 30))
        surface = Surface(20, 30)
        panel.paint(surface)
        rows = ["".join(cell.char for cell in row) for row in surface._rows]
        assert rows[0].startswith("  ______")
        assert all(len(row) == 20 for row in rows)

    def test_a_panel_shorter_than_the_banner_does_not_crash(self):
        from pigit.app_graph_panel import _BANNER_H

        _, panel = self._panel()
        panel.resize((40, _BANNER_H - 1))
        assert panel._board.viewport_size[1] == 0
        panel.paint(Surface(40, _BANNER_H - 1))

    def test_resize_relays_out_the_board(self):
        """Wrapping follows the width, so the panel has to forward resizes."""
        _, panel = self._panel()
        panel.resize((240, 30))
        wide = panel._board.content_size
        panel.resize((80, 30))
        narrow = panel._board.content_size

        assert narrow[0] < wide[0]
        assert narrow[1] > wide[1]


class TestScrollLeftMarker:
    """The right edge has always said "…"; the left edge said nothing."""

    def _row(self, d, s):
        return "".join(c.char for c in s.rows()[1])

    def test_no_marker_while_unscrolled(self):
        d = DiffViewer()
        d.set_content(["+added line here"])
        d.resize((30, 5))
        s = Surface(30, 5)
        d.paint(s)
        assert "‹" not in self._row(d, s)

    def test_marker_appears_once_scrolled_left(self):
        d = DiffViewer()
        d.set_content(["+added line here"])
        d.resize((30, 5))
        d._max_col_offset = 10
        d._col_offset = 4
        s = Surface(30, 5)
        d.paint(s)
        row = self._row(d, s)
        # Column 6 = 1 (border) + 4 (gutter) + 1 (prefix); the +/- sign owns
        # column 5, so the marker reserves the first column of the text area.
        assert row[6] == "‹"
        assert row[5] == "+"  # the prefix is not borrowed

    def test_the_marker_reserves_a_column_rather_than_overlaying_text(self):
        """The marker costs one column of content, exactly like the right-edge
        "…" — it must not sit on top of the first character of the line."""
        d = DiffViewer()
        d.set_content(["abcdefghijklmnopqrstuvwxyz"])
        d.resize((30, 5))
        d._max_col_offset = 20
        d._col_offset = 6
        s = Surface(30, 5)
        d.paint(s)
        row = self._row(d, s)
        assert row[6] == "‹"
        # A plain scroll by 6 would put "g" here (line[6]); the marker shifts
        # the content one column further, so line[7] leads instead.
        assert row[7] == "h"
