# -*- coding: utf-8 -*-
"""
Module: pigit/app_preview.py
Description: Large-screen Status/Stash side panel hosting DiffViewer with async loads.
Author: Zev
Date: 2026-05-26
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal
from collections.abc import Callable

from pigit.termui import (
    AsyncTask,
    EVT_SELECTION_CHANGED,
    Component,
    MouseEvent,
    Surface,
    is_on_visible_paint_path,
    render_child,
    run_async,
)
from pigit.termui.types import PreviewPayload

from .app_diff import DiffType, DiffViewer

if TYPE_CHECKING:
    from .viewmodels.status import IStatusViewModel


@dataclass(frozen=True)
class _PreviewRequest:
    """Captured UI-thread selection for an async diff load.

    Status previews are keyed by worktree path (``key``), never by a list
    index that can drift when ``StatusViewModel`` refreshes.
    """

    kind: Literal["status", "stash"]
    key: str
    title: str
    diff_type: DiffType
    stash_ref: str | None = None


class PreviewPanel(Component):
    """Host that loads Status/Stash diffs into a full-size DiffViewer.

    Chrome is DiffViewer's own box; this panel wires selection to content via
    async ``load_diff`` / ``load_stash_diff`` with a stale-guard key.
    """

    def __init__(
        self,
        *,
        status_vm: IStatusViewModel | None = None,
        on_preview_target: Callable[[str | None], None] | None = None,
        x: int = 1,
        y: int = 1,
        size: tuple[int, int] | None = None,
        id: str | None = None,
    ) -> None:
        super().__init__(x, y, size, id=id)
        self._status_vm = status_vm
        self._on_preview_target = on_preview_target
        self._diff_viewer = DiffViewer(
            x=1,
            y=1,
            id="preview_diff",
            word_diff=True,
        )
        self._unsubs: list[Callable[[], None]] = []
        self._load_task: AsyncTask[list[str]] | None = None
        self._request: _PreviewRequest | None = None

    def mount(self) -> None:
        """Activate the inner diff viewer and subscribe to selection changes."""
        super().mount()
        self._diff_viewer.mount()
        self._unsubs.append(self.subscribe(EVT_SELECTION_CHANGED, self._on_selection))

    def unmount(self) -> None:
        """Cancel loads, unsubscribe, and unmount the inner diff viewer."""
        self._cancel_load()
        self._set_preview_target(None)
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()
        self._diff_viewer.unmount()
        super().unmount()

    def set_vm(self, vm: IStatusViewModel | None) -> None:
        """Retarget this panel to a new Status ViewModel (repo session switch).

        Selection subscription stays on the EventBus; only the VM pointer changes.
        Cancels in-flight loads and clears stale preview content.
        """
        self._cancel_load()
        self._request = None
        self._status_vm = vm
        if self.is_mounted():
            self._set_preview_target(None)
            self.clear()

    def _on_selection(self, *, active: Component | None = None, **_) -> bool:
        """Start an async diff load for the active PreviewPayload panel."""
        self._cancel_load()
        if not isinstance(active, PreviewPayload):
            self._request = None
            self._set_preview_target(None)
            self.clear()
            return True

        request = self._capture_request(active)
        if request is None:
            self._request = None
            self._set_preview_target(None)
            self.clear()
            return True

        self._request = request
        if request.kind == "status":
            self._set_preview_target(request.key)
        else:
            self._set_preview_target(None)

        self._load_task = run_async(
            lambda: self._load_lines(request),
            lambda lines: self._on_loaded(request, lines),
        )
        return True

    def reload(self) -> None:
        """Re-fetch the last Status/Stash preview (observe ``PREVIEW_FILE`` sink)."""
        request = self._request
        if request is None or self._status_vm is None:
            return
        if self._load_task is not None:
            self._load_task.cancel()
            self._load_task = None
        self._request = request
        self._load_task = run_async(
            lambda: self._load_lines(request),
            lambda lines: self._on_loaded(request, lines),
        )

    def _capture_request(self, active: PreviewPayload) -> _PreviewRequest | None:
        """Snapshot selection on the UI thread before background work."""
        from .app_stash import StashPanel
        from .app_status import StatusPanel

        title = active.preview_title()
        if not title:
            return None

        if isinstance(active, StatusPanel):
            hit = active.file_at_cursor()
            if hit is None:
                return None
            file, _ = hit
            diff_type = DiffType.STAGED
            if hasattr(active, "preview_diff_type"):
                diff_type = active.preview_diff_type()
            return _PreviewRequest(
                kind="status",
                key=file.get_file_str(),
                title=title,
                diff_type=diff_type,
            )

        if isinstance(active, StashPanel):
            stash = active._current_stash()
            if stash is None:
                return None
            return _PreviewRequest(
                kind="stash",
                key=stash.ref,
                title=title,
                diff_type=DiffType.STASH,
                stash_ref=stash.ref,
            )

        return None

    def _load_lines(self, request: _PreviewRequest) -> list[str]:
        """Background: load diff lines for a captured request."""
        vm = self._status_vm
        if vm is None:
            return []
        if request.kind == "status":
            return vm.load_diff_by_path(request.key)
        if request.kind == "stash" and request.stash_ref is not None:
            return vm.load_stash_diff(request.stash_ref)
        return []

    def _on_loaded(self, request: _PreviewRequest, lines: list[str]) -> None:
        """Apply a completed load if the selection key is still current."""
        if not self.is_mounted() or not is_on_visible_paint_path(self):
            return
        if self._request is None or self._request.key != request.key:
            return
        if not lines:
            self.clear()
            return
        self.set_diff_type(request.diff_type)
        self._diff_viewer.set_box_title(request.title)
        self._diff_viewer.set_content(lines)

    def _cancel_load(self) -> None:
        """Invalidate any in-flight load so its result is dropped."""
        if self._load_task is not None:
            self._load_task.cancel()
            self._load_task = None

    def _set_preview_target(self, rel: str | None) -> None:
        """Notify the app of the Status file path used for observe classify."""
        if self._on_preview_target is not None:
            self._on_preview_target(rel)

    def set_preview(
        self, diff_lines: list[str], title: str, subtitle: str = ""
    ) -> None:
        """Load diff lines and put ``title`` / ``subtitle`` on the viewer's box."""
        label = title if not subtitle else f"{title}  {subtitle}"
        self._diff_viewer.set_box_title(label)
        self._diff_viewer.set_content(diff_lines)

    def set_diff_type(self, diff_type: DiffType) -> None:
        """Set the diff type on the inner viewer."""
        self._diff_viewer.set_diff_type(diff_type)

    def clear(self) -> None:
        """Clear the inner viewer."""
        self._diff_viewer.set_box_title("")
        self._diff_viewer.set_content([])

    def resize(self, size: tuple[int, int]) -> None:
        """Give the inner DiffViewer the full preview size."""
        self._size = size
        self._diff_viewer.x = 1
        self._diff_viewer.y = 1
        self._diff_viewer.resize(size)

    def scroll_down(self, step: int = 1) -> None:
        """Scroll the inner diff viewer down."""
        self._diff_viewer.scroll_down(step)

    def scroll_up(self, step: int = 1) -> None:
        """Scroll the inner diff viewer up."""
        self._diff_viewer.scroll_up(step)

    def handle_mouse(self, event: MouseEvent) -> bool:
        """Wheel-scroll the inner diff; clicks are ignored (preview is not focused)."""
        return self._diff_viewer.handle_mouse(event)

    def paint(self, surface: Surface) -> None:
        render_child(self._diff_viewer, surface, "PreviewPanel")
