"""
Module: pigit/termui/widgets/toast.py
Description: Auto-dismissing notification toast component (TOAST layer).
Author: Zev
Date: 2026-05-18
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING
from collections.abc import Callable, Sequence

from .._component import Component
from .._frame import BoxFrame
from .._segment import Segment
from .._surface import Surface, _Subsurface
from ..types import ToastPosition, OverlayDispatchResult
from ..wcwidth_table import truncate_by_width, wcswidth

if TYPE_CHECKING:
    from ..event_loop import AppEventLoop

MAX_TOAST_LINES = 100


class Toast(Component):
    """Auto-dismissing notification message (TOAST layer) with border, animation, and configurable position."""

    def __init__(
        self,
        message: str = "",
        *,
        segments: Sequence[Segment] | None = None,
        duration: float = 2.0,
        size: tuple[int, int] | None = None,
        clock: Callable[[], float] = time.monotonic,
        position: ToastPosition = ToastPosition.TOP_RIGHT,
        enter_duration: float = 0.5,
        exit_duration: float = 0.5,
    ) -> None:
        super().__init__(size=size)
        self._segments: list[Segment] = (
            list(segments) if segments else [Segment(message)]
        )
        self.duration = duration
        self._clock = clock
        self._position = position

        if enter_duration + exit_duration > duration:
            enter_duration = 0.0
            exit_duration = 0.0
        self._enter_duration = enter_duration
        self._exit_duration = exit_duration

        self._created_at = self._clock()
        self.open = True

        self._term_size: tuple[int, int] = (0, 0)
        self._needs_rebuild = True
        self._frame: BoxFrame | None = None
        self._lines: list[str] = []
        self._outer_w = 0
        self.outer_row_count = 0

        self._event_loop: AppEventLoop | None = None
        self._timer_id: int | None = None

    def is_expired(self) -> bool:
        """Return True if the toast has exceeded its display duration."""
        return self._clock() - self._created_at > self.duration + self._exit_duration

    def resize(self, size: tuple[int, int]) -> None:
        """Resize the toast and mark it for rebuild if the size changed."""
        new_size = (int(size[0]), int(size[1]))
        if self._term_size != new_size:
            self._term_size = new_size
            self._needs_rebuild = True
        super().resize(size)

    def _rebuild_frame(self) -> None:
        """Rebuild BoxFrame and content lines based on current terminal size."""
        max_inner_w = max(0, self._term_size[0] - 4)
        line_segments: list[list[Segment]] = [[]]
        for seg in self._segments:
            parts = seg.text.split("\n")
            for i, part in enumerate(parts):
                if i > 0:
                    line_segments.append([])
                if part:
                    line_segments[-1].append(
                        Segment(part, fg=seg.fg, bg=seg.bg, style_flags=seg.style_flags)
                    )
        truncated: list[list[Segment]] = []
        inner_w = 0
        for line in line_segments[:MAX_TOAST_LINES]:
            line_w = 0
            new_line: list[Segment] = []
            for seg in line:
                seg_w = wcswidth(seg.text)
                if line_w + seg_w > max_inner_w:
                    avail = max(0, max_inner_w - line_w)
                    if avail > 0:
                        truncated_text = truncate_by_width(seg.text, avail)
                        new_line.append(
                            Segment(
                                truncated_text,
                                fg=seg.fg,
                                bg=seg.bg,
                                style_flags=seg.style_flags,
                            )
                        )
                        line_w += wcswidth(truncated_text)
                    break
                new_line.append(seg)
                line_w += seg_w
            truncated.append(new_line)
            inner_w = max(inner_w, line_w)

        self._line_segments = truncated
        inner_h = len(self._line_segments)

        if self._frame is None:
            self._frame = BoxFrame(inner_w, inner_h)
        else:
            self._frame.set_inner_size(inner_w, inner_h)
        self._outer_w = self._frame.outer_width
        self.outer_row_count = self._frame.outer_height
        self._needs_rebuild = False

    def _compute_slide_offset(self, elapsed: float) -> int:
        """Compute horizontal animation offset."""
        total = self.duration
        enter = self._enter_duration
        exit = self._exit_duration
        dist = self._outer_w + 1 if self._outer_w > 0 else 2

        is_left = self._position in (ToastPosition.TOP_LEFT, ToastPosition.BOTTOM_LEFT)
        direction = -1 if is_left else 1

        if enter == 0 and exit == 0:
            return 0

        if elapsed < enter and enter > 0:
            progress = elapsed / enter
            return direction * int(dist * (1.0 - progress))
        if elapsed > total - exit and exit > 0:
            progress = max(0.0, (total - elapsed) / exit)
            return direction * int(dist * (1.0 - progress))
        return 0

    def _compute_base_position(self, surface) -> tuple[int, int]:
        """Compute the target (row, col) without animation offset."""
        if self._position in (ToastPosition.TOP_LEFT, ToastPosition.TOP_RIGHT):
            base_row = 1
        else:
            base_row = max(0, surface.height - self.outer_row_count - 1)

        if self._position in (ToastPosition.TOP_LEFT, ToastPosition.BOTTOM_LEFT):
            base_col = 1
        else:
            base_col = max(0, surface.width - self._outer_w - 1)

        return base_row, base_col

    def dispatch_overlay_key(self, key: str) -> OverlayDispatchResult:
        """Drop all keys; toasts are non-interactive."""
        return OverlayDispatchResult.DROPPED_UNBOUND

    def _start_animation_timer(self) -> None:
        """Register a short-interval timer to drive enter/exit animation."""
        loop = self._event_loop
        if loop is None or self._timer_id is not None:
            return

        def _tick() -> None:
            if not self.open or self.is_expired():
                self._stop_animation_timer()
                return
            loop.request_render()

        self._timer_id = loop.add_interval(0.05, _tick)

    def _stop_animation_timer(self) -> None:
        """Cancel the animation timer, if active."""
        if self._timer_id is not None and self._event_loop is not None:
            self._event_loop.remove_interval(self._timer_id)
            self._timer_id = None

    def _render_surface(self, surface: Surface | _Subsurface) -> None:
        if not self.open:
            return

        if surface.width < 4 or surface.height < 3:
            return

        if self._needs_rebuild:
            self._rebuild_frame()

        if self._frame is None:
            return

        # Ensure animation timer is running on first render.
        if self._timer_id is None:
            self._start_animation_timer()

        elapsed = self._clock() - self._created_at
        offset_x = self._compute_slide_offset(elapsed)
        base_row, base_col = self._compute_base_position(surface)
        render_col = base_col + offset_x

        if base_row + self.outer_row_count <= 0 or base_row >= surface.height:
            return
        if render_col + self._outer_w <= 0 or render_col >= surface.width:
            return

        self._frame.draw(surface, base_row, render_col)
        content_row, content_col, cw, _ch = self._frame.content_rect(
            base_row, render_col
        )
        for i, segments in enumerate(self._line_segments):
            row = content_row + i
            if row >= surface.height:
                break
            surface.draw_segments(row, content_col, segments)
            line_text = "".join(s.text for s in segments)
            line_w = wcswidth(line_text)
            pad_col = content_col + line_w
            pad_w = content_col + cw - pad_col
            if pad_w > 0:
                surface.fill_rect_rgb(row, pad_col, pad_w, 1)

    @property
    def message(self) -> str:
        """Toast message content (backward compatibility)."""
        return "".join(s.text for s in self._segments)

    def hide(self) -> None:
        """Close the toast."""
        self.open = False
        self._stop_animation_timer()

    def refresh(self) -> None:
        """No-op refresh for compatibility."""
