# -*- coding: utf-8 -*-
"""
Module: tests/termui/test_split_pane.py
Description: Tests for SplitPane attach/detach and width layout.
Author: Zev
Date: 2026-08-20
"""

from __future__ import annotations

import pytest

from pigit.termui.component import Component
from pigit.termui.surface import Surface
from pigit.termui.containers.split_pane import SplitPane


class _Leaf(Component):
    def __init__(self, *, id: str | None = None) -> None:
        super().__init__(id=id)
        self.mounted = False
        self.unmounted = False
        self.sizes: list[tuple[int, int]] = []

    def mount(self) -> None:
        super().mount()
        self.mounted = True

    def unmount(self) -> None:
        self.unmounted = True
        super().unmount()

    def resize(self, size: tuple[int, int]) -> None:
        self._size = size
        self.sizes.append(size)

    def paint(self, surface) -> None:
        pass


@pytest.fixture
def master() -> _Leaf:
    return _Leaf(id="master")


@pytest.fixture
def detail() -> _Leaf:
    return _Leaf(id="detail")


def test_presentation_child_is_master(master: _Leaf, detail: _Leaf) -> None:
    pane = SplitPane(master, detail, id="body")
    assert pane.presentation_child is master


def test_master_only_when_cols_below_breakpoint(master: _Leaf, detail: _Leaf) -> None:
    pane = SplitPane(master, detail, id="body")
    pane.mount()
    pane.resize((100, 20))
    pane.set_detail_wanted(True)
    pane.apply_terminal_width(100)
    assert [c.id for c in pane.children] == ["master"]
    assert master.sizes[-1] == (100, 20)


def test_attaches_detail_on_wide_terminal(master: _Leaf, detail: _Leaf) -> None:
    pane = SplitPane(master, detail, id="body")
    pane.mount()
    pane.resize((140, 20))
    pane.set_detail_wanted(True)
    pane.apply_terminal_width(140)
    assert [c.id for c in pane.children] == ["master", "detail"]
    assert detail.mounted is True
    assert master.sizes[-1][0] == max(60, int(140 * 0.4))
    assert detail.sizes[-1][0] == 140 - master.sizes[-1][0]


def test_master_width_policy_replaces_the_ratio(master: _Leaf, detail: _Leaf) -> None:
    """A policy lets the master grow more slowly than a fixed share would."""
    pane = SplitPane(master, detail, master_width=lambda cols: 70, id="body")
    pane.mount()
    pane.set_detail_wanted(True)
    pane.resize((200, 20))
    pane.apply_terminal_width(200)
    assert master.sizes[-1][0] == 70
    assert detail.sizes[-1][0] == 130


def test_master_width_policy_is_still_clamped(master: _Leaf, detail: _Leaf) -> None:
    low = SplitPane(master, detail, master_width=lambda cols: 10, id="body")
    low.mount()
    low.set_detail_wanted(True)
    low.resize((200, 20))
    low.apply_terminal_width(200)
    assert master.sizes[-1][0] == 60  # the floor

    high = SplitPane(master, detail, master_width=lambda cols: 999, id="other")
    high.mount()
    high.set_detail_wanted(True)
    high.resize((200, 20))
    high.apply_terminal_width(200)
    assert master.sizes[-1][0] == 120  # the cap


def test_master_is_clamped_between_its_floor_and_cap(
    master: _Leaf, detail: _Leaf
) -> None:
    """The floor keeps the list readable where the preview appears; the cap
    hands the surplus to the preview, which is the pane that can use it."""
    pane = SplitPane(master, detail, id="body")
    pane.mount()
    pane.set_detail_wanted(True)
    pane.resize((130, 20))
    pane.apply_terminal_width(130)
    assert master.sizes[-1][0] == 60  # the floor, not 40% of 130
    assert detail.sizes[-1][0] == 70

    pane.resize((400, 20))
    pane.apply_terminal_width(400)
    assert master.sizes[-1][0] == 120  # the cap
    assert detail.sizes[-1][0] == 280


def test_detaches_when_detail_not_wanted(master: _Leaf, detail: _Leaf) -> None:
    pane = SplitPane(master, detail, id="body")
    pane.mount()
    pane.resize((140, 20))
    pane.set_detail_wanted(True)
    pane.apply_terminal_width(140)
    pane.set_detail_wanted(False)
    pane.apply_terminal_width(140)
    assert [c.id for c in pane.children] == ["master"]
    assert detail.unmounted is True


def test_detaches_when_detail_is_none(master: _Leaf, detail: _Leaf) -> None:
    pane = SplitPane(master, detail, id="body")
    pane.mount()
    pane.resize((140, 20))
    pane.set_detail_wanted(True)
    pane.apply_terminal_width(140)
    pane.set_detail(None)
    pane.apply_terminal_width(140)
    assert [c.id for c in pane.children] == ["master"]


def test_toggle_detail_flips_wanted(master: _Leaf, detail: _Leaf) -> None:
    pane = SplitPane(master, detail, id="body")
    pane.mount()
    pane.resize((140, 20))
    pane.set_detail_wanted(True)
    pane.apply_terminal_width(140)
    pane.toggle_detail()
    assert [c.id for c in pane.children] == ["master"]
    pane.toggle_detail()
    assert [c.id for c in pane.children] == ["master", "detail"]


def test_swapping_detail_detaches_old(master: _Leaf, detail: _Leaf) -> None:
    other = _Leaf(id="other")
    pane = SplitPane(master, detail, id="body")
    pane.mount()
    pane.resize((140, 20))
    pane.set_detail_wanted(True)
    pane.apply_terminal_width(140)
    pane.set_detail(other)
    pane.apply_terminal_width(140)
    assert [c.id for c in pane.children] == ["master", "other"]
    assert detail.unmounted is True
    assert other.mounted is True


def test_renders_both_children(master: _Leaf, detail: _Leaf) -> None:
    pane = SplitPane(master, detail, id="body")
    pane.mount()
    pane.resize((140, 10))
    pane.set_detail_wanted(True)
    pane.apply_terminal_width(140)
    surface = Surface(140, 10)
    pane.paint(surface)
