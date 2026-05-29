"""
Module: pigit/termui/widgets/lint_bar.py
Description: Commit message lint bar showing subject/body validation.
Author: Zev
Date: 2026-05-29
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pigit.termui import palette
from pigit.termui._component import Component, bind_signals
from pigit.termui._runtime_context import request_render
from pigit.termui._segment import Segment

if TYPE_CHECKING:
    from pigit.termui._surface import Surface, _Subsurface
    from pigit.termui.widgets import InputLine


class LintBar(Component):
    """One-line lint status bar for commit message editor.

    Subscribes to Subject and Body InputLine value changes and renders
    real-time validation feedback.
    """

    def __init__(
        self,
        subject: InputLine,
        body: InputLine,
        *,
        id: str | None = None,
    ) -> None:
        super().__init__(id=id)
        self._subject = subject
        self._body = body
        self._unsub = bind_signals(
            self,
            subject._value_sig,
            body._value_sig,
            callback=self._on_values_changed,
        )

    def _on_values_changed(self) -> None:
        if self.is_activated():
            request_render()

    def destroy(self) -> None:
        self._unsub()
        super().destroy()

    def _render_surface(self, surface: Surface | _Subsurface) -> None:
        subject = self._subject.value
        body = self._body.value
        segments: list[Segment] = []

        # Subject lint
        subj_len = len(subject)
        if subj_len > 50:
            segments.append(
                Segment(f"Subject {subj_len}/50 ", fg=palette.DEFAULT_FG_DIM)
            )
            segments.append(Segment("✗", fg=palette.RED))
        else:
            segments.append(
                Segment(f"Subject {subj_len}/50 ", fg=palette.DEFAULT_FG_DIM)
            )
            segments.append(Segment("✓", fg=palette.GREEN))

        if subject.endswith("."):
            segments.append(Segment("  trailing period", fg=palette.YELLOW))

        # Body lint
        body_lines = body.split("\n") if body else []
        long_lines = [
            (i + 1, len(line)) for i, line in enumerate(body_lines) if len(line) > 72
        ]
        if long_lines:
            line_no, length = long_lines[0]
            segments.append(
                Segment(
                    f"  │  Body line {line_no}: {length}/72",
                    fg=palette.YELLOW,
                )
            )

        # Render
        col = 0
        for seg in segments:
            if col >= surface.width:
                break
            text = seg.text
            text_width = len(text)
            if col + text_width > surface.width:
                text = text[: surface.width - col]
            surface.draw_text_rgb(0, col, text, fg=seg.fg, style_flags=seg.style_flags)
            col += text_width
