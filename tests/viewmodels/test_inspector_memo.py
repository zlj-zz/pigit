"""
Module: tests/viewmodels/test_inspector_memo.py
Description: Shared ViewModelBase inspector memoization contract.
Author: Zev
Date: 2026-08-26
"""

from __future__ import annotations

from pigit.viewmodels.base import ViewModelBase


class _FakeVM(ViewModelBase[int]):
    """Minimal VM mirroring the inspector wrapper convention used by real VMs."""

    def __init__(self, items: list[int]) -> None:
        super().__init__()
        self._items.set(items)
        self.build_count = 0

    def get_inspector_snapshot(self, idx: int):
        item = self.item_at(idx)
        if item is None:
            return None
        return self._memo_inspector(item, self._build)

    def _build(self):
        self.build_count += 1
        return ("snapshot", self._items.value)


def test_invalid_index_returns_none():
    vm = _FakeVM([1, 2, 3])
    assert vm.get_inspector_snapshot(-1) is None
    assert vm.get_inspector_snapshot(3) is None


def test_memoizes_same_selection():
    vm = _FakeVM([1, 2, 3])
    first = vm.get_inspector_snapshot(0)
    second = vm.get_inspector_snapshot(0)
    assert first is second
    assert vm.build_count == 1


def test_different_selection_rebuilds():
    vm = _FakeVM([1, 2, 3])
    first = vm.get_inspector_snapshot(0)
    second = vm.get_inspector_snapshot(1)
    assert first is not second
    assert vm.build_count == 2


def test_refresh_invalidates_cache():
    vm = _FakeVM([1, 2, 3])
    first = vm.get_inspector_snapshot(0)
    vm._on_loaded([4, 5])
    second = vm.get_inspector_snapshot(0)
    assert first is not second
    assert second == ("snapshot", [4, 5])
    assert vm.build_count == 2
