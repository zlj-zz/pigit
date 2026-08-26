# -*- coding: utf-8 -*-
"""
Module: tests/app/test_stash_panel.py
Description: Tests for StashPanel section header and list rendering.
Author: Zev
Date: 2026-08-17
"""

from __future__ import annotations

from unittest.mock import Mock, patch

from pigit.app_stash import StashPanel
from pigit.git.model import Stash
from pigit.termui import palette
from pigit.termui.surface import Surface
from pigit.termui.reactive import Signal
from pigit.viewmodels.base import ActionResult
from pigit.viewmodels.status import IStatusViewModel


def _panel_with_stashes(msgs: list[str]) -> StashPanel:
    vm = Mock(spec=IStatusViewModel)
    vm.items = Signal([])
    vm.load_stashes.return_value = [
        Stash(ref=f"stash@{{{i}}}", sha=f"abc{i}", msg=msg)
        for i, msg in enumerate(msgs)
    ]
    panel = StashPanel(vm=vm)
    panel.mount()
    panel.on_focus()
    return panel


def test_section_header_right_label_with_tail():
    """Top row is fill dashes, bold Stash, then two trailing dashes."""
    from pigit.app_theme import THEME
    from pigit.termui.theme import get_theme, set_theme

    prev = get_theme()
    set_theme(THEME)
    try:
        panel = _panel_with_stashes(["WIP on main"])
        panel.resize((40, 6))
        surface = Surface(40, 6)
        panel.paint(surface)

        row = "".join(c.char for c in surface._rows[0]).rstrip("\x00").rstrip()
        assert row.endswith("Stash ──")
        assert "─" in row
        label_start = row.index("Stash")
        for col in range(label_start, label_start + 5):
            assert surface._rows[0][col].style_flags & palette.STYLE_BOLD
            assert surface._rows[0][col].fg == THEME.fg_panel_title
    finally:
        set_theme(prev)


def test_describe_row_puts_ref_on_right():
    from pigit.app_theme import THEME
    from pigit.termui.theme import get_theme, set_theme

    prev = get_theme()
    set_theme(THEME)
    try:
        panel = _panel_with_stashes(["WIP on main"])
        left, main, right = panel.describe_row(0, is_cursor=True)
        assert "".join(s.text for s in main) == "WIP on main"
        assert "".join(s.text for s in right) == "stash@{0}"
        assert right[0].fg == THEME.fg_muted
        assert main[0].fg == THEME.fg_primary
    finally:
        set_theme(prev)


def test_visible_row_count_excludes_header():
    panel = _panel_with_stashes(["a", "b", "c"])
    panel.resize((40, 5))
    assert panel.visible_row_count == 4


def test_drop_requires_confirmation():
    """Drop shows an ERROR-kind alert and only drops when confirmed."""
    vm = Mock()
    vm.items = Signal([])
    vm.load_stashes.return_value = [
        Stash(ref="stash@{0}", sha="abc0", msg="WIP on main")
    ]
    vm.stash_drop = Mock()
    panel = StashPanel(vm=vm)
    panel.mount()
    panel.on_focus()
    panel.curr_no = 0

    with patch("pigit.app_stash.AlertDialog.alert") as alert:
        panel.drop()
        # No drop before the user confirms.
        vm.stash_drop.assert_not_called()
        alert.assert_called_once()
        args, kwargs = alert.call_args
        assert "stash@{0}" in args[0]
        from pigit.termui import FeedbackKind

        assert kwargs["kind"] is FeedbackKind.ERROR

        # Confirming performs the drop; cancelling does not.
        args[1](False)
        vm.stash_drop.assert_not_called()
        args[1](True)
        vm.stash_drop.assert_called_once_with("stash@{0}")


def test_drop_empty_list_is_noop():
    vm = Mock()
    vm.items = Signal([])
    vm.load_stashes.return_value = []
    vm.stash_drop = Mock()
    panel = StashPanel(vm=vm)
    panel.mount()
    panel.on_focus()
    with patch("pigit.app_stash.AlertDialog.alert") as alert:
        panel.drop()
        alert.assert_not_called()
        vm.stash_drop.assert_not_called()


def test_section_rule_follows_panel_focus():
    """Stash header rule follows the owning panel's presentation (brand when
    focused); the chrome slot itself is never a focus leaf."""
    from pigit.app_theme import THEME
    from pigit.termui._layer import LayerKind
    from pigit.termui._runtime_context import (
        RuntimeContext,
        _runtime_ctx,
        reset_focus_manager,
        reset_overlay_host,
        set_focus_manager,
        set_overlay_host,
    )
    from pigit.termui.component import Component
    from pigit.termui.root import ComponentRoot
    from pigit.termui.theme import get_theme, set_theme

    prev = get_theme()
    set_theme(THEME)
    runtime = RuntimeContext()
    token = _runtime_ctx.set(runtime)
    try:
        vm = Mock(spec=IStatusViewModel)
        vm.items = Signal([])
        vm.load_stashes.return_value = []
        stash = StashPanel(vm=vm)
        root = ComponentRoot(stash)
        root.resize((40, 12))
        set_overlay_host(root)
        set_focus_manager(root._focus_manager)

        # Focus on the stash panel: rule uses brand accent.
        root._focus_manager.set_focus_chain(stash)
        assert stash.is_presentation_active() is True
        assert stash._header._rule_fg() == THEME.fg_accent

        # Focus elsewhere: rule dims.
        other = Component()
        root._focus_manager.set_focus_chain(other)
        assert stash.is_presentation_active() is False
        assert stash._header._rule_fg() == THEME.fg_dim

        # Overlay steal dims even while focused.
        root._focus_manager.set_focus_chain(stash)

        class _Sheet(Component):
            open = True

            def paint(self, surface) -> None:
                pass

        root._layer_stack.push(LayerKind.MODAL, _Sheet())
        assert root.is_presentation_stolen() is True
        assert stash._header._rule_fg() == THEME.fg_dim
    finally:
        reset_overlay_host()
        reset_focus_manager()
        _runtime_ctx.reset(token)
        set_theme(prev)


def test_apply_keeps_stash_without_confirmation():
    vm = Mock()
    vm.items = Signal([])
    vm.load_stashes.return_value = [
        Stash(ref="stash@{0}", sha="abc0", msg="WIP on main")
    ]
    vm.stash_apply = Mock(
        return_value=ActionResult(success=True, message="Applied stash")
    )
    panel = StashPanel(vm=vm)
    panel.mount()
    panel.on_focus()
    panel.curr_no = 0
    with patch("pigit.app_stash.show_badge"):
        panel.apply()
    vm.stash_apply.assert_called_once_with("stash@{0}")
    vm.stash_pop.assert_not_called()


def test_get_inspector_snapshot_delegates_to_vm():
    vm = Mock(spec=IStatusViewModel)
    vm.items = Signal([])
    vm.load_stashes.return_value = [
        Stash(ref="stash@{0}", sha="abc0", msg="WIP on main")
    ]
    vm.get_stash_snapshot.return_value = object()
    panel = StashPanel(vm=vm)
    panel.mount()
    panel.on_focus()
    panel.curr_no = 0
    assert panel.get_inspector_snapshot() is vm.get_stash_snapshot.return_value
    vm.get_stash_snapshot.assert_called_once_with("stash@{0}")


def test_get_inspector_snapshot_empty_is_none():
    vm = Mock(spec=IStatusViewModel)
    vm.items = Signal([])
    vm.load_stashes.return_value = []
    panel = StashPanel(vm=vm)
    panel.mount()
    assert panel.get_inspector_snapshot() is None


def test_apply_empty_list_is_noop():
    vm = Mock()
    vm.items = Signal([])
    vm.load_stashes.return_value = []
    vm.stash_apply = Mock()
    panel = StashPanel(vm=vm)
    panel.mount()
    panel.apply()
    vm.stash_apply.assert_not_called()
