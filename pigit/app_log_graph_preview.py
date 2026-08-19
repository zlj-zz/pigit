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
    BoxFrame,
    EVT_SELECTION_CHANGED,
    Component,
    MouseEvent,
    parse_ansi_line,
    run_async,
    Segment,
)
from pigit.termui.wcwidth_table import truncate_by_width, wcswidth
from pigit.termui.widgets.line_text_browser import LineTextBrowser

from .app_theme import THEME
from .git.api import GitError

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
        x: int = 1,
        y: int = 1,
        size: tuple[int, int] | None = None,
        id: str | None = None,
    ) -> None:
        super().__init__(x, y, size, id=id)
        self._vm = vm
        self._title = _EMPTY_TITLE
        self._frame = BoxFrame(0, 0, title=self._title, fg=THEME.fg_dim)
        self._browser = LineTextBrowser(
            x=2,
            y=2,
            content=[],
            id="log_graph_browser",
        )
        self._styled: list[list[Segment]] = []
        self._unsubs: list[Callable[[], None]] = []
        self._load_task: AsyncTask[list[str]] | None = None
        self._requested_branch: str | None = None

    def activate(self) -> None:
        """Activate the graph browser and subscribe to selection changes."""
        super().activate()
        self._browser.activate()
        self._unsubs.append(self.subscribe(EVT_SELECTION_CHANGED, self._on_selection))

    def deactivate(self) -> None:
        """Cancel any pending load, unsubscribe, and deactivate the browser."""
        self._cancel_load()
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()
        self._browser.deactivate()
        super().deactivate()

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
            lambda lines: self._on_graph_loaded(name, lines),
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
        if not self.is_activated():
            return
        if self._requested_branch != name:
            return
        self.set_lines(lines, title=name)

    def set_lines(self, lines: list[str], title: str) -> None:
        """Replace graph content and reset scroll to the top.

        ANSI in ``lines`` is parsed once into segments for drawing; the
        inner browser keeps the stripped text for scroll metrics.
        """
        self._title = title
        self._frame.title = title
        self._styled = [parse_ansi_line(line) for line in lines]
        self._browser._content = [
            "".join(seg.text for seg in row) for row in self._styled
        ]
        self._browser._i = 0

    def clear(self) -> None:
        """Clear graph content and restore the empty title."""
        self.set_lines([], title=_EMPTY_TITLE)

    def resize(self, size: tuple[int, int]) -> None:
        """Size the border frame and inner browser to ``size``."""
        self._size = size
        inner_w = max(1, size[0] - 2)
        inner_h = max(1, size[1] - 2)
        self._frame.set_inner_size(inner_w, inner_h)
        self._browser.x = 2
        self._browser.y = 2
        self._browser.resize((inner_w, inner_h))

    def scroll_down(self, step: int = 1) -> None:
        """Scroll the graph down by ``step`` lines."""
        self._browser.scroll_down(step)

    def scroll_up(self, step: int = 1) -> None:
        """Scroll the graph up by ``step`` lines."""
        self._browser.scroll_up(step)

    def handle_mouse(self, event: MouseEvent) -> bool:
        """Wheel-scroll the inner browser; clicks are ignored."""
        return self._browser.handle_mouse(event)

    def _render_surface(self, surface) -> None:
        """Draw the dim border, then the parsed graph segments inside it."""
        w = surface.width
        h = surface.height
        if w < 2 or h < 2:
            return
        inner_h = max(1, h - 2)
        inner_w = max(1, w - 2)
        self._frame.set_inner_size(inner_w, inner_h)
        self._frame.title = self._title
        self._frame.draw(surface, 0, 0)
        start = self._browser._i
        visible = self._styled[start : start + inner_h]
        for idx, segs in enumerate(visible):
            surface.draw_segments(1 + idx, 1, self._clip_segments(segs, inner_w))

    @staticmethod
    def _clip_segments(segs: list[Segment], max_width: int) -> list[Segment]:
        """Clip styled segments to *max_width* display columns.

        The trailing segment is truncated so content never overwrites the
        right-hand frame border.
        """
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
