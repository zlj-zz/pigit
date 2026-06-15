"""
Tests for PreviewPanel selection-changed subscriber.
"""

from __future__ import annotations

import pytest

from pigit.app_diff import DiffType
from pigit.app_preview import PreviewPanel
from pigit.app_stash import StashPanel
from pigit.app_status import StatusPanel
from pigit.git.model import File, Stash
from pigit.termui import ActionEventType, Component
from pigit.termui._root import ComponentRoot
from pigit.termui.event_bus import EventBus


class _FakeStatusVM:
    def __init__(self) -> None:
        self.diff_calls: list[int] = []
        self.stash_diff_calls: list[str] = []
        self.diff_return: list[str] = ["diff line"]
        self.stash_diff_return: list[str] = ["stash diff line"]

    def load_diff(self, idx: int, plain: bool = True) -> list[str]:
        self.diff_calls.append(idx)
        return list(self.diff_return)

    def load_stash_diff(self, ref: str) -> list[str]:
        self.stash_diff_calls.append(ref)
        return list(self.stash_diff_return)


class _FakeStatusPanel(StatusPanel):
    tab_name = "Status"
    tab_key = "1"

    def __init__(self, files: list[File], curr_no: int, source_index: int) -> None:
        from pigit.termui.reactive import Signal

        self._curr_no_sig = Signal(curr_no)
        self._r_start_sig = Signal(0)
        self.files = files
        self._source_index = source_index

    def filter_source_index(self, visible_idx: int | None = None) -> int:
        return self._source_index


class _FakeStashPanel(StashPanel):
    tab_name = "Stash"
    tab_key = "3"

    def __init__(self, stashes: list[Stash], curr_no: int) -> None:
        from pigit.termui.reactive import Signal

        self._curr_no_sig = Signal(curr_no)
        self._r_start_sig = Signal(0)
        self.stashes = stashes


@pytest.fixture
def preview() -> PreviewPanel:
    return PreviewPanel(status_vm=_FakeStatusVM(), id="preview")


def _mount(bus: EventBus, preview: PreviewPanel) -> ComponentRoot:
    root = ComponentRoot(preview, event_bus=bus)
    preview.activate()
    return root


def test_clears_when_active_is_not_status_or_stash(preview: PreviewPanel) -> None:
    bus = EventBus()
    _mount(bus, preview)

    preview.set_preview(["old"], title="Old", subtitle="sub")
    bus.publish(ActionEventType.selection_changed, active=Component())

    assert preview._title == "Preview"
    assert preview._subtitle == ""
    assert preview._diff_viewer._content == []


def test_loads_file_diff_for_status_panel(preview: PreviewPanel) -> None:
    bus = EventBus()
    _mount(bus, preview)
    vm = preview._status_vm
    assert isinstance(vm, _FakeStatusVM)

    file = File(
        name="src/main.py",
        display_str="src/main.py",
        short_status="M ",
        has_staged_change=True,
        has_unstaged_change=False,
        tracked=True,
        deleted=False,
        added=False,
        has_merged_conflicts=False,
        has_inline_merged_conflicts=False,
    )
    active = _FakeStatusPanel([file], curr_no=0, source_index=7)

    bus.publish(ActionEventType.selection_changed, active=active)

    assert vm.diff_calls == [7]
    assert preview._title == "src/main.py"
    assert preview._subtitle == "Staged"
    assert preview._diff_viewer._diff_type is DiffType.STAGED
    assert preview._diff_viewer._content == ["diff line"]


def test_loads_stash_diff_for_stash_panel(preview: PreviewPanel) -> None:
    bus = EventBus()
    _mount(bus, preview)
    vm = preview._status_vm
    assert isinstance(vm, _FakeStatusVM)

    stash = Stash(ref="stash@{0}", sha="abc123", msg="WIP")
    active = _FakeStashPanel([stash], curr_no=0)

    bus.publish(ActionEventType.selection_changed, active=active)

    assert vm.stash_diff_calls == ["stash@{0}"]
    assert preview._title == "WIP"
    assert preview._subtitle == "stash@{0}"
    assert preview._diff_viewer._diff_type is DiffType.STASH
    assert preview._diff_viewer._content == ["stash diff line"]


def test_deactivate_unsubscribes(preview: PreviewPanel) -> None:
    bus = EventBus()
    _ = _mount(bus, preview)
    vm = preview._status_vm
    assert isinstance(vm, _FakeStatusVM)

    file = File(
        name="a.py",
        display_str="a.py",
        short_status=" M",
        has_staged_change=False,
        has_unstaged_change=True,
        tracked=True,
        deleted=False,
        added=False,
        has_merged_conflicts=False,
        has_inline_merged_conflicts=False,
    )
    active = _FakeStatusPanel([file], curr_no=0, source_index=0)

    bus.publish(ActionEventType.selection_changed, active=active)
    assert vm.diff_calls == [0]
    assert preview._title == "a.py"

    preview.deactivate()
    del vm.diff_calls[:]

    other = _FakeStatusPanel(
        [File(
            name="b.py",
            display_str="b.py",
            short_status=" M",
            has_staged_change=False,
            has_unstaged_change=True,
            tracked=True,
            deleted=False,
            added=False,
            has_merged_conflicts=False,
            has_inline_merged_conflicts=False,
        )],
        curr_no=0,
        source_index=0,
    )
    bus.publish(ActionEventType.selection_changed, active=other)

    assert vm.diff_calls == []
    assert preview._title == "a.py"
