# -*- coding: utf-8 -*-
"""
Module: pigit/app_log_graph_preview.py
Description: 大屏 Branch 页只读 git log --graph 预览面板。
Author: Zev
Date: 2026-08-18
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from pigit.termui import (
    AsyncTask,
    EVT_SELECTION_CHANGED,
    Component,
    MouseEvent,
    Surface,
    is_on_visible_paint_path,
    run_async,
    Segment,
)
from pigit.termui.primitives import parse_ansi_line
from pigit.termui.wcwidth_table import truncate_by_width, wcswidth
from pigit.termui.widgets import BorderedTextBrowser

from .git.api import GitError
from .app_types import guard_or_identity

if TYPE_CHECKING:
    from .viewmodels.branch import IBranchViewModel

_EMPTY_TITLE = "Log"
_EMPTY_GRAPH = "No commits"


class LogGraphPreview(Component):
    """Bordered, read-only native git log --graph viewer for the Branch tab."""

    SCROLL_PAGE_SIZE = 5

    def __init__(
        self,
        *,
        vm: IBranchViewModel,
        guard_async: Callable[[Callable[[list[str]], None]], Callable[[list[str]], None]]
        | None = None,
        x: int = 1,
        y: int = 1,
        size: tuple[int, int] | None = None,
        id: str | None = None,
    ) -> None:
        super().__init__(x, y, size, id=id)
        self._vm = vm
        self._guard_async = guard_async
        self._frame_browser = BorderedTextBrowser(
            title=_EMPTY_TITLE, id="log_graph_browser"
        )
        self._unsubs: list[Callable[[], None]] = []
        self._load_task: AsyncTask[list[str]] | None = None
        self._requested_branch: str | None = None

    @property
    def _browser(self):
        """Inner TextBrowser (test and scroll helpers)."""
        return self._frame_browser._browser

    @property
    def _title(self) -> str:
        return self._frame_browser._title

    def mount(self) -> None:
        """Activate the graph browser and subscribe to selection changes."""
        super().mount()
        self._frame_browser.mount()
        self._unsubs.append(self.subscribe(EVT_SELECTION_CHANGED, self._on_selection))

    def unmount(self) -> None:
        """Cancel any pending load, unsubscribe, and unmount the browser."""
        self._cancel_load()
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()
        self._frame_browser.unmount()
        super().unmount()

    def set_vm(self, vm: IBranchViewModel) -> None:
        """Retarget this panel to a new Branch ViewModel (repo session switch).

        Selection subscription stays on the EventBus; only the VM pointer changes.
        Cancels in-flight loads and clears stale graph content.
        """
        self._cancel_load()
        self._requested_branch = None
        self._vm = vm
        if self.is_mounted():
            self.clear()

    def _on_selection(self, *, active: Component | None = None, **_) -> bool:
        """Start a background graph load for the selected branch."""
        from .app_branch import BranchPanel

        self._cancel_load()
        if not isinstance(active, BranchPanel):
            self.clear()
            return True
        if not active.branches or not (0 <= active.curr_no < len(active.branches)):
            self.clear()
            return True

        name = active.branches[active.curr_no].name
        self._requested_branch = name
        self._load_task = run_async(
            lambda: self._load_graph(name),
            guard_or_identity(self._guard_async, lambda lines: self._on_graph_loaded(name, lines)),
        )
        return True

    def _cancel_load(self) -> None:
        """Invalidate any in-flight load so its result is dropped."""
        self._requested_branch = None
        if self._load_task is not None:
            self._load_task.cancel()
            self._load_task = None

    def _load_graph(self, name: str) -> list[str]:
        """Background: fetch graph lines; a failure renders inline."""
        try:
            lines = self._vm.load_log_graph(name)
        except GitError as e:
            return [f"{name}: {e}"]
        return lines if lines else [_EMPTY_GRAPH]

    def _on_graph_loaded(self, name: str, lines: list[str]) -> None:
        """Apply a completed graph load if the selection is still current."""
        if not self.is_mounted() or not is_on_visible_paint_path(self):
            return
        if self._requested_branch != name:
            return
        self.set_lines(lines, title=name)

    def reload(self) -> None:
        """Re-fetch the graph for the last requested branch (observe sink)."""
        name = self._requested_branch
        if not name:
            return
        if self._load_task is not None:
            self._load_task.cancel()
            self._load_task = None
        self._requested_branch = name
        self._load_task = run_async(
            lambda: self._load_graph(name),
            guard_or_identity(self._guard_async, lambda lines: self._on_graph_loaded(name, lines)),
        )

    def set_lines(self, lines: list[str], title: str) -> None:
        """Replace graph content and reset scroll to the top."""
        self._frame_browser.set_title(title)
        styled = [parse_ansi_line(line) for line in lines]
        width = self._size[0] if self._size else 0
        if width > 2:
            inner_w = width - 2
            styled = [self._clip_segments(row, inner_w) for row in styled]
        self._frame_browser.set_content(styled)

    def clear(self) -> None:
        """Clear graph content and restore the empty title."""
        self.set_lines([], title=_EMPTY_TITLE)

    def resize(self, size: tuple[int, int]) -> None:
        """Size the bordered browser to ``size``."""
        self._size = size
        self._frame_browser.x = 1
        self._frame_browser.y = 1
        self._frame_browser.resize(size)

    def scroll_down(self, step: int = 1) -> None:
        """Scroll the graph down by ``step`` lines."""
        self._frame_browser.scroll_down(step)

    def scroll_up(self, step: int = 1) -> None:
        """Scroll the graph up by ``step`` lines."""
        self._frame_browser.scroll_up(step)

    def handle_mouse(self, event: MouseEvent) -> bool:
        """Wheel-scroll the inner browser; clicks are ignored."""
        return self._frame_browser.handle_mouse(event)

    def paint(self, surface: Surface) -> None:
        self._frame_browser.paint(surface)

    @staticmethod
    def _clip_segments(segs: list[Segment], max_width: int) -> list[Segment]:
        """Clip styled segments to *max_width* display columns."""
        out: list[Segment] = []
        used = 0
        for seg in segs:
            seg_w = wcswidth(seg.text)
            if used + seg_w <= max_width:
                out.append(seg)
                used += seg_w
                continue
            if used < max_width:
                out.append(
                    Segment(
                        truncate_by_width(seg.text, max_width - used),
                        fg=seg.fg,
                        bg=seg.bg,
                        style_flags=seg.style_flags,
                    )
                )
            break
        return out
