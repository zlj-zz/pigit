"""
Module: pigit/termui/widgets/input_line.py
Description: Single-line text input widget with completion support.
Author: Zev
Date: 2026-05-16
"""

from __future__ import annotations

from collections.abc import Callable

from .. import keys, palette
from .._component import Component
from .._runtime_context import get_focus_manager, request_render
from .._surface import Surface, _Subsurface
from ..reactive import Signal
from ..tty_io import truncate_line
from ..types import OverlayDispatchResult
from ..wcwidth_table import pad_by_width, truncate_by_width, wcswidth


class InputLine(Component):
    """Single-line text input.

    ``max_length`` limits Unicode code points (not display width).
    When placed inside a layout container (e.g. ``Column``), ``x`` and ``y``
    are managed by the container and manual values are ignored.
    """

    def __init__(
        self,
        prompt: str = "",
        placeholder: str = "",
        visible: bool = True,
        overlay_mode: bool = False,
        allow_newline: bool = True,
        max_length: int | None = None,
        activate_key: str = "/",
        cancel_key: str = keys.KEY_ESC,
        *,
        on_value_changed: Callable[[str], None] | None = None,
        on_submit: Callable[[str], None] | None = None,
        on_cancel: Callable[[], None] | None = None,
        on_activate: Callable[[], None] | None = None,
        candidate_provider: Callable[[str], list[str]] | None = None,
        x: int = 1,
        y: int = 1,
        size: tuple[int, int] | None = None,
    ) -> None:
        super().__init__(x=x, y=y, size=size)

        self._prompt = prompt
        self._placeholder = placeholder
        self._visible = visible
        self._overlay_mode = overlay_mode
        self._allow_newline = allow_newline
        self._max_length = max_length
        self._activate_key = activate_key
        self._cancel_key = cancel_key
        self._on_change = on_value_changed
        self._on_submit = on_submit
        self._on_cancel = on_cancel
        self._on_activate = on_activate
        self._value_sig = Signal("")
        self._cursor_sig = Signal(0)
        self._cached_lines: list[str] = [""]
        self._cached_line_offsets: list[int] = [0]
        self._unsubs: list[Callable[[], None]] = []
        self._unsubs.append(self._value_sig.subscribe(self._update_cache_and_notify))
        self._unsubs.append(
            self._cursor_sig.subscribe(lambda _: self._request_render())
        )
        # Completion state
        self._candidate_provider = candidate_provider
        self._candidates: list[str] = []
        self._candidate_idx = 0
        self._showing_candidates = False
        self._original_value = ""
        self._scroll_offset = 0

    def _request_render(self) -> None:
        """Request a render if this component is currently activated."""
        if self.is_activated():
            request_render()

    def destroy(self) -> None:
        """Unsubscribe from signals and tear down."""
        for unsub in self._unsubs:
            unsub()
        super().destroy()

    @property
    def value(self) -> str:
        """Return the current input value."""
        return self._value_sig.value

    @property
    def cursor(self) -> int:
        """Return the current cursor position."""
        return self._cursor_sig.value

    @property
    def prompt(self) -> str:
        """Return the current prompt text."""
        return self._prompt

    def set_value(self, text: str) -> None:
        """Replace current value and move cursor to end."""
        if self._max_length:
            text = text[: self._max_length]
        if self._value_sig.value == text:
            return
        self._value_sig.set(text)
        self._cursor_sig.set(len(self._value_sig.value))

    @property
    def is_visible(self) -> bool:
        """Return whether the input line is currently visible."""
        return self._visible

    def set_visible(self, visible: bool) -> None:
        """Toggle whether the input line is visible."""
        self._visible = visible

    def insert(self, ch: str) -> None:
        """Insert a character at the current cursor position."""
        if self._max_length and len(self._value_sig.value) >= self._max_length:
            return
        v = self._value_sig.value
        c = self._cursor_sig.value
        self._value_sig.set(v[:c] + ch + v[c:])
        self._cursor_sig.set(c + 1)

    # ------------------------------------------------------------------
    # Cache & line/col helpers (multiline support)
    # ------------------------------------------------------------------

    def _update_cache_and_notify(self, value: str) -> None:
        """Update cached lines/offsets when value changes, then request render."""
        self._cached_lines = value.split("\n")
        self._cached_line_offsets = [0]
        offset = 0
        for line in self._cached_lines[:-1]:
            offset += len(line) + 1
            self._cached_line_offsets.append(offset)
        if self._on_change:
            self._on_change(value)
        self._request_render()

    def _to_line_col(self, offset: int) -> tuple[int, int]:
        """Global character offset -> (line, col), 0-based."""
        offsets = self._cached_line_offsets
        lines = self._cached_lines
        # Bisect to find the line containing offset
        lo, hi = 0, len(offsets)
        while lo < hi:
            mid = (lo + hi) // 2
            if offsets[mid] <= offset:
                lo = mid + 1
            else:
                hi = mid
        line = lo - 1
        if line < 0:
            line = 0
        col = offset - offsets[line]
        # Clamp col to line length (handles offset at very end)
        col = min(col, len(lines[line]))
        return line, col

    def _from_line_col(self, line: int, col: int) -> int:
        """(line, col) -> global character offset."""
        lines = self._cached_lines
        line = max(0, min(line, len(lines) - 1))
        return self._cached_line_offsets[line] + min(col, len(lines[line]))

    # ------------------------------------------------------------------
    # Cursor movement (multiline)
    # ------------------------------------------------------------------

    def cursor_up(self) -> None:
        """Move cursor to previous line, preserving column if possible."""
        line, col = self._to_line_col(self._cursor_sig.value)
        if line > 0:
            prev_len = len(self._cached_lines[line - 1])
            self._cursor_sig.set(self._from_line_col(line - 1, min(col, prev_len)))

    def cursor_down(self) -> None:
        """Move cursor to next line, preserving column if possible."""
        line, col = self._to_line_col(self._cursor_sig.value)
        if line < len(self._cached_lines) - 1:
            next_len = len(self._cached_lines[line + 1])
            self._cursor_sig.set(self._from_line_col(line + 1, min(col, next_len)))

    def cursor_line_start(self) -> None:
        """Move cursor to start of current line."""
        line, _ = self._to_line_col(self._cursor_sig.value)
        self._cursor_sig.set(self._from_line_col(line, 0))

    def cursor_line_end(self) -> None:
        """Move cursor to end of current line."""
        line, _ = self._to_line_col(self._cursor_sig.value)
        self._cursor_sig.set(self._from_line_col(line, len(self._cached_lines[line])))

    # ------------------------------------------------------------------
    # Editing (multiline-aware)
    # ------------------------------------------------------------------

    def delete(self) -> None:
        """Delete character after cursor (merges lines at end-of-line)."""
        c = self._cursor_sig.value
        v = self._value_sig.value
        if c >= len(v):
            return
        line, col = self._to_line_col(c)
        # At end of line (but not last line): merge with next line
        if col == len(self._cached_lines[line]) and line < len(self._cached_lines) - 1:
            lines = list(self._cached_lines)
            lines[line] = lines[line] + lines[line + 1]
            del lines[line + 1]
            self._value_sig.set("\n".join(lines))
            return
        # Normal delete
        self._value_sig.set(v[:c] + v[c + 1 :])

    def backspace(self) -> None:
        """Delete character before cursor (merges lines at start-of-line)."""
        c = self._cursor_sig.value
        if c == 0:
            return
        line, col = self._to_line_col(c)
        # At start of line (but not first line): merge with previous line
        if col == 0 and line > 0:
            lines = list(self._cached_lines)
            prev, curr = lines[line - 1], lines[line]
            lines[line - 1] = prev + curr
            del lines[line]
            self._value_sig.set("\n".join(lines))
            self._cursor_sig.set(self._from_line_col(line - 1, len(prev)))
            return
        # Normal backspace
        v = self._value_sig.value
        self._value_sig.set(v[: c - 1] + v[c:])
        self._cursor_sig.set(c - 1)

    def home(self) -> None:
        """Move cursor to start of current line."""
        self.cursor_line_start()

    def end(self) -> None:
        """Move cursor to end of current line."""
        self.cursor_line_end()

    def clear(self) -> None:
        """Clear the input value and reset the cursor."""
        self._value_sig.set("")
        self._cursor_sig.set(0)
        if self._on_change:
            self._on_change(self._value_sig.value)

    def set_prompt(self, prompt: str) -> None:
        """Switch prompt text at runtime."""
        self._prompt = prompt

    def set_candidate_provider(
        self, provider: Callable[[str], list[str]] | None
    ) -> None:
        """Switch or clear the candidate provider at runtime.

        When ``provider`` is *None*, the *Tab* key behaves as a plain key.
        """
        self._candidate_provider = provider
        self._candidates = []
        self._candidate_idx = 0
        self._showing_candidates = False

    def on_key(self, key: str) -> None:
        """Process keyboard input for this input line.

        Callers (e.g. ``Application`` subclasses) are responsible for
        ensuring this method is only invoked when the input line is active.
        """
        if self._overlay_mode and not self._visible:
            if key == self._activate_key:
                self._enter_overlay_mode()
                return

        # ── Enter / Shift+Enter ──────────────────────────────────────────
        if key in (keys.KEY_ENTER, keys.KEY_SHIFT_ENTER):
            is_shift = key == keys.KEY_SHIFT_ENTER
            # Candidate list takes priority for plain Enter
            if not is_shift and self._showing_candidates:
                self._value_sig.set(self._candidates[self._candidate_idx])
                self._cursor_sig.set(len(self._value_sig.value))
                self._showing_candidates = False
                self._candidates = []
                return
            # on_submit (Enter only, not Shift+Enter)
            if not is_shift and self._on_submit:
                self._on_submit(self._value_sig.value)
                return
            # Insert newline if allowed
            if self._allow_newline:
                self.insert("\n")
            return

        # ── Esc ──────────────────────────────────────────────────────────
        if key == keys.KEY_ESC:
            if self._showing_candidates:
                self._value_sig.set(self._original_value)
                self._cursor_sig.set(len(self._value_sig.value))
                self._showing_candidates = False
                self._candidates = []
                return
            if self._overlay_mode and self._visible:
                self._exit_overlay_mode()
                return
            if self._on_cancel:
                self._on_cancel()
            return

        # ── Tab / Shift+Tab (completion) ─────────────────────────────────
        if key in (keys.KEY_TAB, keys.KEY_SHIFT_TAB) and self._candidate_provider:
            if not self._showing_candidates:
                self._showing_candidates = True
                self._original_value = self._value_sig.value
                self._candidates = self._candidate_provider(self._value_sig.value)
                self._candidate_idx = 0
            else:
                step = 1 if key == keys.KEY_TAB else -1
                self._candidate_idx = max(
                    0, min(self._candidate_idx + step, len(self._candidates) - 1)
                )
            if self._candidates:
                self._value_sig.set(self._candidates[self._candidate_idx])
                self._cursor_sig.set(len(self._value_sig.value))
            return

        # ── Up / Down ────────────────────────────────────────────────────
        if key in (keys.KEY_UP, keys.KEY_DOWN):
            if self._showing_candidates:
                step = -1 if key == keys.KEY_UP else 1
                self._candidate_idx = max(
                    0, min(self._candidate_idx + step, len(self._candidates) - 1)
                )
                self._value_sig.set(self._candidates[self._candidate_idx])
                self._cursor_sig.set(len(self._value_sig.value))
                return
            if key == keys.KEY_UP:
                self.cursor_up()
            else:
                self.cursor_down()
            return

        # ── Plain text editing ───────────────────────────────────────────
        if key == keys.KEY_BACKSPACE:
            self.backspace()
        elif key == keys.KEY_DELETE:
            self.delete()
        elif key == keys.KEY_LEFT:
            self.cursor_left()
        elif key == keys.KEY_RIGHT:
            self.cursor_right()
        elif key == keys.KEY_HOME:
            self.home()
        elif key == keys.KEY_END:
            self.end()
        elif len(key) == 1 and key.isprintable() and ord(key) >= 32:
            self.insert(key)

    def dispatch_overlay_key(self, key: str) -> OverlayDispatchResult:
        """Route keys to this input line when it is inside an overlay (Sheet/Popup)."""
        self.on_key(key)
        return OverlayDispatchResult.HANDLED_EXPLICIT

    def cursor_left(self) -> None:
        """Move the cursor one position to the left."""
        self._cursor_sig.set(max(0, self._cursor_sig.value - 1))

    def cursor_right(self) -> None:
        """Move the cursor one position to the right."""
        self._cursor_sig.set(
            min(len(self._value_sig.value), self._cursor_sig.value + 1)
        )

    def _render_surface(self, surface: Surface | _Subsurface) -> None:
        if not self._visible:
            return
        value = self._value_sig.value
        cursor = self._cursor_sig.value
        cursor_line, cursor_col = self._to_line_col(cursor)
        lines = self._cached_lines
        visible_rows = surface.height

        # ── Scroll offset: keep cursor visible ───────────────────────────
        if len(lines) <= visible_rows:
            start_line = 0
        else:
            start_line = max(0, cursor_line - visible_rows + 1)
        self._scroll_offset = start_line

        # ── Candidate inline-completion (single-line, no scroll) ─────────
        if self._showing_candidates and self._candidates:
            self._render_candidates(surface, value)
            return

        # ── Multi-line text rendering ────────────────────────────────────
        for row in range(visible_rows):
            line_idx = start_line + row
            if line_idx >= len(lines):
                # Empty row
                surface.draw_text_rgb(
                    row,
                    0,
                    " " * surface.width,
                    fg=palette.DEFAULT_FG,
                    bg=palette.DEFAULT_BG,
                )
                continue

            line = lines[line_idx]
            if line_idx == 0:
                # First row: prompt + line content (or placeholder when empty)
                prefix = self._prompt
                prefix_wc = wcswidth(prefix)
                if not line and self._placeholder:
                    # Prompt in normal color, placeholder in dim
                    avail = max(0, surface.width - prefix_wc)
                    ph = truncate_by_width(self._placeholder, avail)
                    surface.draw_text_rgb(
                        row, 0, prefix, fg=palette.DEFAULT_FG, bg=palette.DEFAULT_BG
                    )
                    if ph:
                        surface.draw_text_rgb(
                            row,
                            prefix_wc,
                            ph,
                            fg=palette.DEFAULT_FG_DIM,
                            bg=palette.DEFAULT_BG,
                        )
                    # Pad rest of row
                    pad = surface.width - prefix_wc - wcswidth(ph)
                    if pad > 0:
                        surface.draw_text_rgb(
                            row,
                            surface.width - pad,
                            " " * pad,
                            fg=palette.DEFAULT_FG,
                            bg=palette.DEFAULT_BG,
                        )
                else:
                    text = prefix + line
                    text = truncate_by_width(text, surface.width)
                    text = pad_by_width(text, surface.width)
                    surface.draw_text_rgb(
                        row,
                        0,
                        text,
                        fg=palette.DEFAULT_FG,
                        bg=palette.DEFAULT_BG,
                    )
                if self.is_focus_leaf and cursor_line == 0:
                    self._draw_block_cursor(
                        surface,
                        row,
                        prefix_wc + wcswidth(line[:cursor_col]),
                        line,
                        cursor_col,
                    )
            else:
                # Subsequent rows: no prompt
                text = truncate_by_width(line, surface.width)
                text = pad_by_width(text, surface.width)
                surface.draw_text_rgb(
                    row,
                    0,
                    text,
                    fg=palette.DEFAULT_FG,
                    bg=palette.DEFAULT_BG,
                )
                if self.is_focus_leaf and cursor_line == line_idx:
                    self._draw_block_cursor(
                        surface, row, wcswidth(line[:cursor_col]), line, cursor_col
                    )

    def _render_candidates(self, surface: Surface | _Subsurface, value: str) -> None:
        """Render inline completion candidate (single-line mode)."""
        match_len = len(self._original_value)
        matched = value[:match_len]
        suffix = value[match_len:]
        prefix = f"{self._prompt}{matched}"
        avail = surface.width - len(prefix)
        if avail < 0:
            prefix = prefix[: surface.width - 1] + "…" if surface.width > 0 else ""
            suffix = ""
        elif len(suffix) > avail:
            suffix = suffix[:avail]
        surface.draw_text_rgb(
            0, 0, prefix, fg=palette.DEFAULT_FG, bg=palette.DEFAULT_BG
        )
        if suffix:
            surface.draw_text_rgb(
                0,
                len(prefix),
                suffix,
                fg=palette.DEFAULT_FG_DIM,
                bg=palette.DEFAULT_BG,
            )
        if self.is_focus_leaf:
            cursor_abs = len(prefix) + len(suffix)
            if cursor_abs < surface.width:
                surface.draw_text_rgb(
                    0,
                    cursor_abs,
                    " ",
                    fg=palette.DEFAULT_BG,
                    bg=palette.DEFAULT_FG,
                )

    def _draw_block_cursor(
        self,
        surface: Surface | _Subsurface,
        row: int,
        cursor_x: int,
        line: str,
        cursor_col: int,
    ) -> None:
        """Draw a single-character block cursor at (row, cursor_x)."""
        if cursor_x >= surface.width:
            return
        ch = line[cursor_col] if cursor_col < len(line) else " "
        surface.draw_text_rgb(
            row, cursor_x, ch, fg=palette.DEFAULT_BG, bg=palette.DEFAULT_FG
        )

    def _enter_overlay_mode(self) -> None:
        """Activate overlay mode: show input and grab focus."""
        self._visible = True
        self.clear()
        fm = get_focus_manager()
        if fm is not None:
            fm.focus_grab(self)
        if self._on_activate:
            self._on_activate()

    def _exit_overlay_mode(self) -> None:
        """Exit overlay mode: hide input and release focus."""
        self._visible = False
        fm = get_focus_manager()
        if fm is not None:
            fm.focus_release()
        if self._on_cancel:
            self._on_cancel()
