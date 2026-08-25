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
        self.activated = False
        self.deactivated = False
        self.sizes: list[tuple[int, int]] = []

    def activate(self) -> None:
        super().activate()
        self.activated = True

    def deactivate(self) -> None:
        self.deactivated = True
        super().deactivate()

    def resize(self, size: tuple[int, int]) -> None:
        self._size = size
        self.sizes.append(size)

    def _render_surface(self, surface) -> None:
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
    pane.activate()
    pane.resize((100, 20))
    pane.set_detail_wanted(True)
    pane.apply_terminal_width(100)
    assert [c.id for c in pane.children] == ["master"]
    assert master.sizes[-1] == (100, 20)


def test_attaches_detail_on_wide_terminal(master: _Leaf, detail: _Leaf) -> None:
    pane = SplitPane(master, detail, id="body")
    pane.activate()
    pane.resize((140, 20))
    pane.set_detail_wanted(True)
    pane.apply_terminal_width(140)
    assert [c.id for c in pane.children] == ["master", "detail"]
    assert detail.activated is True
    assert master.sizes[-1][0] == max(50, int(140 * 0.35))
    assert detail.sizes[-1][0] == 140 - master.sizes[-1][0]


def test_detaches_when_detail_not_wanted(master: _Leaf, detail: _Leaf) -> None:
    pane = SplitPane(master, detail, id="body")
    pane.activate()
    pane.resize((140, 20))
    pane.set_detail_wanted(True)
    pane.apply_terminal_width(140)
    pane.set_detail_wanted(False)
    pane.apply_terminal_width(140)
    assert [c.id for c in pane.children] == ["master"]
    assert detail.deactivated is True


def test_detaches_when_detail_is_none(master: _Leaf, detail: _Leaf) -> None:
    pane = SplitPane(master, detail, id="body")
    pane.activate()
    pane.resize((140, 20))
    pane.set_detail_wanted(True)
    pane.apply_terminal_width(140)
    pane.set_detail(None)
    pane.apply_terminal_width(140)
    assert [c.id for c in pane.children] == ["master"]


def test_toggle_detail_flips_wanted(master: _Leaf, detail: _Leaf) -> None:
    pane = SplitPane(master, detail, id="body")
    pane.activate()
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
    pane.activate()
    pane.resize((140, 20))
    pane.set_detail_wanted(True)
    pane.apply_terminal_width(140)
    pane.set_detail(other)
    pane.apply_terminal_width(140)
    assert [c.id for c in pane.children] == ["master", "other"]
    assert detail.deactivated is True
    assert other.activated is True


def test_renders_both_children(master: _Leaf, detail: _Leaf) -> None:
    pane = SplitPane(master, detail, id="body")
    pane.activate()
    pane.resize((140, 10))
    pane.set_detail_wanted(True)
    pane.apply_terminal_width(140)
    surface = Surface(140, 10)
    pane._render_surface(surface)
