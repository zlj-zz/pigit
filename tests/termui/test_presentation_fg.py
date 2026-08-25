"""
Module: tests/termui/test_presentation_fg.py
Description: Presentation-active / steal / focus-leaf rules for Component.presentation_fg.
Author: Zev
Date: 2026-08-24
"""

from __future__ import annotations

import pytest

from pigit.termui import palette
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
from pigit.termui.theme import Theme, get_theme, set_theme
from pigit.termui.widgets import Toast


@pytest.fixture(autouse=True)
def _runtime_context():
    """Fresh RuntimeContext; clear overlay host and focus manager after each test."""
    runtime = RuntimeContext()
    token = _runtime_ctx.set(runtime)
    yield
    reset_overlay_host()
    reset_focus_manager()
    _runtime_ctx.reset(token)


class _Body(Component):
    def paint(self, surface) -> None:
        pass


class _SheetChild(Component):
    def paint(self, surface) -> None:
        pass


def test_presentation_fg_active_without_host() -> None:
    theme = get_theme()
    body = _Body()
    assert body.presentation_fg("primary") == theme.fg_primary
    assert body.presentation_fg("muted") == theme.fg_muted


def test_sheet_open_steals_and_dims_body() -> None:
    theme = get_theme()
    body = _Body()
    root = ComponentRoot(body)
    root.resize((80, 24))
    set_overlay_host(root)
    set_focus_manager(root._focus_manager)

    assert root.is_presentation_stolen() is False
    assert body.presentation_fg("primary") == theme.fg_primary

    root.show_sheet(_SheetChild(), height=4)
    assert root.is_presentation_stolen() is True
    assert body.presentation_fg("primary") == theme.fg_inactive
    assert body.presentation_fg("muted") == theme.fg_inactive

    root.dismiss_sheet()
    assert root.is_presentation_stolen() is False
    assert body.presentation_fg("primary") == theme.fg_primary
    assert body.presentation_fg("muted") == theme.fg_muted


def test_sheet_open_body_focus_chain_still_inactive() -> None:
    """Body click may restore focus leaf; steal still dims structural fg."""
    theme = get_theme()
    body = _Body()
    root = ComponentRoot(body)
    root.resize((80, 24))
    set_overlay_host(root)
    set_focus_manager(root._focus_manager)
    root.show_sheet(_SheetChild(), height=4)

    root._focus_manager.set_focus_chain(body)
    assert body.is_focus_leaf is True
    assert root.is_presentation_stolen() is True
    assert body.presentation_fg("primary") == theme.fg_inactive


def test_non_focus_leaf_softens_without_steal() -> None:
    """Co-visible sibling (Status/Stash): not leaf → primary→muted, muted→dim."""
    theme = get_theme()
    status = _Body()
    stash = _Body()
    root = ComponentRoot(status)
    root.resize((80, 24))
    set_overlay_host(root)
    set_focus_manager(root._focus_manager)
    root._focus_manager.set_focus_chain(status)
    stash._focus_level = -1

    assert status.is_presentation_active() is True
    assert status.presentation_fg("primary") == theme.fg_primary
    assert stash.is_focus_leaf is False
    assert stash.is_presentation_stolen() is False
    assert stash.is_presentation_active() is False
    assert stash.presentation_fg("primary") == theme.fg_muted
    assert stash.presentation_fg("muted") == theme.fg_dim


def test_toast_alone_does_not_steal() -> None:
    theme = get_theme()
    body = _Body()
    root = ComponentRoot(body)
    root.resize((80, 24))
    set_overlay_host(root)
    set_focus_manager(root._focus_manager)

    toast = Toast("spin", duration=3600.0)
    toast.open = True
    root._layer_stack.push(LayerKind.TOAST, toast)

    assert root.has_overlay_open() is True
    assert root.is_presentation_stolen() is False
    assert body.presentation_fg("primary") == theme.fg_primary


def test_modal_steals_presentation() -> None:
    theme = get_theme()
    body = _Body()
    root = ComponentRoot(body)
    root.resize((80, 24))
    set_overlay_host(root)
    set_focus_manager(root._focus_manager)

    class _Modal(Component):
        open = True

        def paint(self, surface) -> None:
            pass

    root._layer_stack.push(LayerKind.MODAL, _Modal())
    assert root.is_presentation_stolen() is True
    assert body.presentation_fg("primary") == theme.fg_inactive


def test_fg_inactive_on_base_theme() -> None:
    assert Theme().fg_inactive == palette.SLATE
    custom = Theme(fg_inactive=(9, 9, 9))
    old = get_theme()
    set_theme(custom)
    try:
        body = _Body()
        root = ComponentRoot(body)
        root.resize((40, 12))
        set_overlay_host(root)
        root.show_sheet(_SheetChild(), height=3)
        assert body.presentation_fg("primary") == (9, 9, 9)
    finally:
        set_theme(old)
