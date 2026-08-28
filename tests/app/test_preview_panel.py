"""
Tests for PreviewPanel selection-changed subscriber.
"""

from __future__ import annotations

import pytest

from pigit.app_diff import DiffType, DiffViewer
from pigit.app_preview import PreviewPanel
from pigit.app_stash import StashPanel
from pigit.app_status import StatusPanel
from pigit.git.model import File, Stash
from pigit.termui import EVT_SELECTION_CHANGED, Component
from pigit.termui.mouse import MouseButton, MouseEvent, MouseKind
from pigit.termui.root import ComponentRoot
from pigit.termui.surface import Surface
from pigit.termui.event_bus import EventBus


class _FakeStatusVM:
    def __init__(self) -> None:
        self.diff_calls: list[int] = []
        self.diff_path_calls: list[str] = []
        self.stash_diff_calls: list[str] = []
        self.diff_return: list[str] = ["diff line"]
        self.stash_diff_return: list[str] = ["stash diff line"]

    def load_diff(
        self, idx: int, plain: bool = True, word_diff: bool = False
    ) -> list[str]:
        self.diff_calls.append(idx)
        return list(self.diff_return)

    def load_diff_by_path(
        self, rel: str, plain: bool = True, word_diff: bool = False
    ) -> list[str]:
        self.diff_path_calls.append(rel)
        return list(self.diff_return)

    def load_stash_diff(self, ref: str, word_diff: bool = False) -> list[str]:
        self.stash_diff_calls.append(ref)
        return list(self.stash_diff_return)


class _FakeStatusPanel(StatusPanel):
    TAB_NAME = "Status"
    tab_key = "1"

    def __init__(
        self, files: list[File], curr_no: int, source_index: int, vm: _FakeStatusVM
    ) -> None:
        from pigit.termui.reactive import Signal

        self._curr_no_sig = Signal(curr_no)
        self._r_start_sig = Signal(0)
        self.files = files
        self._source_index = source_index
        self._vm = vm

    def file_at_cursor(self):
        if self.files and 0 <= self.curr_no < len(self.files):
            return self.files[self.curr_no], self._source_index
        return None


class _FakeStashPanel(StashPanel):
    TAB_NAME = "Stash"
    tab_key = "3"

    def __init__(self, stashes: list[Stash], curr_no: int, vm: _FakeStatusVM) -> None:
        from pigit.termui.reactive import Signal

        self._curr_no_sig = Signal(curr_no)
        self._r_start_sig = Signal(0)
        self.stashes = stashes
        self._vm = vm


class _FakeTask:
    def cancel(self) -> None:
        pass


def _run_sync(work, callback):
    callback(work())
    return _FakeTask()


@pytest.fixture(autouse=True)
def _sync_async(monkeypatch):
    monkeypatch.setattr("pigit.app_preview.run_async", _run_sync)


@pytest.fixture
def preview() -> PreviewPanel:
    return PreviewPanel(status_vm=_FakeStatusVM(), id="preview")


def _mount(bus: EventBus, preview: PreviewPanel) -> ComponentRoot:
    root = ComponentRoot(preview, event_bus=bus)
    preview.mount()
    return root


def test_clears_when_active_is_not_status_or_stash(preview: PreviewPanel) -> None:
    bus = EventBus()
    _mount(bus, preview)

    preview.set_preview(["old"], title="Old", subtitle="sub")
    bus.publish(EVT_SELECTION_CHANGED, active=Component())

    assert preview._diff_viewer._box_title == ""
    assert preview._diff_viewer._lines == []


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
    active = _FakeStatusPanel([file], curr_no=0, source_index=7, vm=vm)

    bus.publish(EVT_SELECTION_CHANGED, active=active)

    assert vm.diff_path_calls == ["src/main.py"]
    assert vm.diff_calls == []
    assert "src/main.py" in preview._diff_viewer._box_title
    assert "Staged" in preview._diff_viewer._box_title
    assert preview._diff_viewer._diff_type is DiffType.STAGED
    assert preview._diff_viewer._lines == ["diff line"]


def test_same_selection_does_not_reload(preview: PreviewPanel) -> None:
    """Re-emitting the same Status selection must not cancel+reload (no flicker)."""
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
    active = _FakeStatusPanel([file], curr_no=0, source_index=7, vm=vm)
    bus.publish(EVT_SELECTION_CHANGED, active=active)
    assert vm.diff_path_calls == ["src/main.py"]
    first_task = preview._load_task
    first_lines = list(preview._diff_viewer._lines)

    bus.publish(EVT_SELECTION_CHANGED, active=active)
    assert vm.diff_path_calls == ["src/main.py"]
    assert preview._load_task is first_task
    assert preview._diff_viewer._lines == first_lines


def test_different_selection_reloads(preview: PreviewPanel) -> None:
    """Switching to another file starts a new load."""
    bus = EventBus()
    _mount(bus, preview)
    vm = preview._status_vm
    assert isinstance(vm, _FakeStatusVM)

    file_a = File(
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
    file_b = File(
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
    )
    bus.publish(
        EVT_SELECTION_CHANGED,
        active=_FakeStatusPanel([file_a], curr_no=0, source_index=0, vm=vm),
    )
    assert vm.diff_path_calls == ["a.py"]
    vm.diff_return = ["diff b"]
    bus.publish(
        EVT_SELECTION_CHANGED,
        active=_FakeStatusPanel([file_b], curr_no=0, source_index=1, vm=vm),
    )
    assert vm.diff_path_calls == ["a.py", "b.py"]
    assert preview._diff_viewer._lines == ["diff b"]
    assert "b.py" in preview._diff_viewer._box_title


def test_loads_stash_diff_for_stash_panel(preview: PreviewPanel) -> None:
    bus = EventBus()
    _mount(bus, preview)
    vm = preview._status_vm
    assert isinstance(vm, _FakeStatusVM)

    stash = Stash(ref="stash@{0}", sha="abc123", msg="WIP")
    active = _FakeStashPanel([stash], curr_no=0, vm=vm)

    bus.publish(EVT_SELECTION_CHANGED, active=active)

    assert vm.stash_diff_calls == ["stash@{0}"]
    assert "WIP" in preview._diff_viewer._box_title
    assert "stash@{0}" in preview._diff_viewer._box_title
    assert preview._diff_viewer._diff_type is DiffType.STASH
    assert preview._diff_viewer._lines == ["stash diff line"]


def test_stale_guard_drops_outdated_preview_apply(monkeypatch) -> None:
    """A superseded async load must not overwrite a newer selection."""
    targets: list[str | None] = []
    vm = _FakeStatusVM()
    preview = PreviewPanel(
        status_vm=vm,
        on_preview_target=targets.append,
        id="preview",
    )
    bus = EventBus()
    _mount(bus, preview)

    pending: list[tuple] = []

    def _defer(work, callback):
        pending.append((work, callback))
        return _FakeTask()

    monkeypatch.setattr("pigit.app_preview.run_async", _defer)

    file_a = File(
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
    file_b = File(
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
    )
    bus.publish(
        EVT_SELECTION_CHANGED,
        active=_FakeStatusPanel([file_a], curr_no=0, source_index=0, vm=vm),
    )
    bus.publish(
        EVT_SELECTION_CHANGED,
        active=_FakeStatusPanel([file_b], curr_no=0, source_index=1, vm=vm),
    )
    assert len(pending) == 2
    assert targets[-1] == "b.py"

    vm.diff_return = ["from a"]
    work_a, cb_a = pending[0]
    cb_a(work_a())
    assert preview._diff_viewer._lines == []

    vm.diff_return = ["from b"]
    work_b, cb_b = pending[1]
    cb_b(work_b())
    assert preview._diff_viewer._lines == ["from b"]
    assert "b.py" in preview._diff_viewer._box_title


def test_reload_refetches_current_status_preview(preview: PreviewPanel) -> None:
    bus = EventBus()
    _mount(bus, preview)
    vm = preview._status_vm
    assert isinstance(vm, _FakeStatusVM)
    file = File(
        name="src/main.py",
        display_str="src/main.py",
        short_status=" M",
        has_staged_change=False,
        has_unstaged_change=True,
        tracked=True,
        deleted=False,
        added=False,
        has_merged_conflicts=False,
        has_inline_merged_conflicts=False,
    )
    bus.publish(
        EVT_SELECTION_CHANGED,
        active=_FakeStatusPanel([file], curr_no=0, source_index=3, vm=vm),
    )
    assert vm.diff_path_calls == ["src/main.py"]
    vm.diff_return = ["updated"]
    preview.reload()
    assert vm.diff_path_calls == ["src/main.py", "src/main.py"]
    assert vm.diff_calls == []
    assert preview._diff_viewer._lines == ["updated"]


def test_reload_uses_path_not_captured_source_index(preview: PreviewPanel) -> None:
    """After status reorder, reload must not load_diff(stale source_idx)."""
    bus = EventBus()
    _mount(bus, preview)
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
    # Capture with source_index 0; a later list refresh would move a.py.
    bus.publish(
        EVT_SELECTION_CHANGED,
        active=_FakeStatusPanel([file], curr_no=0, source_index=0, vm=vm),
    )
    assert preview._request is not None
    assert preview._request.key == "a.py"
    assert not hasattr(preview._request, "source_idx")
    vm.diff_return = ["still a"]
    preview.reload()
    assert vm.diff_path_calls == ["a.py", "a.py"]
    assert vm.diff_calls == []
    assert preview._diff_viewer._lines == ["still a"]


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
    active = _FakeStatusPanel([file], curr_no=0, source_index=0, vm=vm)

    bus.publish(EVT_SELECTION_CHANGED, active=active)
    assert vm.diff_path_calls == ["a.py"]
    assert "a.py" in preview._diff_viewer._box_title

    preview.unmount()
    del vm.diff_path_calls[:]

    other = _FakeStatusPanel(
        [
            File(
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
            )
        ],
        curr_no=0,
        source_index=0,
        vm=vm,
    )
    bus.publish(EVT_SELECTION_CHANGED, active=other)

    assert vm.diff_path_calls == []
    assert "a.py" in preview._diff_viewer._box_title


def test_inner_diff_fills_preview(preview: PreviewPanel) -> None:
    preview.resize((20, 8))
    assert preview._diff_viewer._size == (20, 8)
    assert preview._diff_viewer.x == 1
    assert preview._diff_viewer.y == 1


def test_preview_title_is_on_diff_box(preview: PreviewPanel) -> None:
    preview.resize((40, 8))
    preview.set_preview(["+ added line"], title="src/main.py", subtitle="Staged")
    surface = Surface(40, 8)
    preview.paint(surface)
    top = surface.lines()[0]
    assert top.startswith("┌")
    assert "src/main.py" in top
    assert "Staged" in top
    assert not hasattr(preview, "_title")


def test_wheel_scrolls_preview_content(preview: PreviewPanel) -> None:
    preview.resize((20, 8))
    preview.set_preview([f"line {i}" for i in range(40)], "file.py")
    assert preview._diff_viewer.scroll_i == 0
    down = MouseEvent(1, 5, MouseButton.WHEEL_DOWN, MouseKind.PRESS)
    assert preview.handle_mouse(down) is True
    assert preview._diff_viewer.scroll_i == DiffViewer.WHEEL_SCROLL_LINES
    up = MouseEvent(1, 1, MouseButton.WHEEL_UP, MouseKind.PRESS)
    assert preview.handle_mouse(up) is True
    assert preview._diff_viewer.scroll_i == 0


def test_preview_ignores_left_click_and_release(preview: PreviewPanel) -> None:
    preview.resize((20, 8))
    preview.set_preview(["a", "b", "c"], "file.py")
    click = MouseEvent(1, 5, MouseButton.LEFT, MouseKind.PRESS)
    assert preview.handle_mouse(click) is False
    release = MouseEvent(1, 5, MouseButton.WHEEL_DOWN, MouseKind.RELEASE)
    assert preview.handle_mouse(release) is False
    assert preview._diff_viewer.scroll_i == 0


def test_set_vm_cancels_inflight_load_and_clears_request() -> None:
    """set_vm drops a pending diff load so its result never lands (D2 step 4)."""
    from unittest.mock import Mock

    panel = PreviewPanel()
    task = Mock()
    panel._load_task = task
    panel._request = object()
    panel.set_vm(Mock())
    task.cancel.assert_called_once()
    assert panel._load_task is None
    assert panel._request is None
