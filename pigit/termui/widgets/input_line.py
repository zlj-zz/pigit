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
from ..wcwidth_table import pad_by_width


class InputLine(Component):
    """Single-line text input.

    ``max_length`` limits Unicode code points (not display width).
    When placed inside a layout container (e.g. ``Column``), ``x`` and ``y``
    are managed by the container and manual values are ignored.
    """

    def __init__(
        self,
        prompt: str = "",
        visible: bool = True,
        max_length: int | None = None,
        on_value_changed: Callable[[str], None] | None = None,
        on_submit: Callable[[str], None] | None = None,
        on_cancel: Callable[[], None] | None = None,
        candidate_provider: Callable[[str], list[str]] | None = None,
        overlay_mode: bool = False,
        activate_key: str = "/",
        cancel_key: str = keys.KEY_ESC,
        on_activate: Callable[[], None] | None = None,
        x: int = 1,
        y: int = 1,
        size: tuple[int, int] | None = None,
    ) -> None:
        super().__init__(x, y, size)

        self._prompt = prompt
        self._visible = visible
        self._max_length = max_length
        self._on_change = on_value_changed
        self._on_submit = on_submit
        self._on_cancel = on_cancel
        self._overlay_mode = overlay_mode
        self._activate_key = activate_key
        self._cancel_key = cancel_key
        self._on_activate = on_activate
        self._value_sig = Signal("")
        self._cursor_sig = Signal(0)
        self._unsubs: list[Callable[[], None]] = []
        self._unsubs.append(self._value_sig.subscribe(lambda _: self._request_render()))
        self._unsubs.append(
            self._cursor_sig.subscribe(lambda _: self._request_render())
        )
        # Completion state
        self._candidate_provider = candidate_provider
        self._candidates: list[str] = []
        self._candidate_idx = 0
        self._showing_candidates = False
        self._original_value = ""

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
        if self._on_change:
            self._on_change(self._value_sig.value)

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
        if self._on_change:
            self._on_change(self._value_sig.value)

    def delete(self) -> None:
        """Delete character after cursor."""
        c = self._cursor_sig.value
        v = self._value_sig.value
        if c < len(v):
            self._value_sig.set(v[:c] + v[c + 1 :])
            if self._on_change:
                self._on_change(self._value_sig.value)

    def backspace(self) -> None:
        """Delete the character before the cursor."""
        c = self._cursor_sig.value
        v = self._value_sig.value
        if c > 0:
            self._value_sig.set(v[: c - 1] + v[c:])
            self._cursor_sig.set(c - 1)
            if self._on_change:
                self._on_change(self._value_sig.value)

    def home(self) -> None:
        """Move cursor to start of line."""
        self._cursor_sig.set(0)

    def end(self) -> None:
        """Move cursor to end of line."""
        self._cursor_sig.set(len(self._value_sig.value))

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
        if key == keys.KEY_ENTER:
            if self._showing_candidates:
                self._value_sig.set(self._candidates[self._candidate_idx])
                self._cursor_sig.set(len(self._value_sig.value))
                self._showing_candidates = False
                self._candidates = []
                return
            if self._on_submit:
                self._on_submit(self._value_sig.value)
            return

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

        if key in (keys.KEY_UP, keys.KEY_DOWN) and self._showing_candidates:
            step = -1 if key == keys.KEY_UP else 1
            self._candidate_idx = max(
                0, min(self._candidate_idx + step, len(self._candidates) - 1)
            )
            self._value_sig.set(self._candidates[self._candidate_idx])
            self._cursor_sig.set(len(self._value_sig.value))
            return

        # Plain text editing
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
        core = f"{self._prompt}{value}"
        prompt_len = len(self._prompt)
        cursor_abs = prompt_len + cursor

        if self._showing_candidates and self._candidates:
            # Inline completion: text already typed by the user stays normal,
            # the rest of the candidate is shown dim.
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
            # Block cursor at the end of the completion text.
            cursor_abs = len(prefix) + len(suffix)
            if cursor_abs < surface.width:
                surface.draw_text_rgb(
                    0, cursor_abs, " ", fg=palette.DEFAULT_BG, bg=palette.DEFAULT_FG
                )
        else:
            text = truncate_line(core, surface.width)
            text = pad_by_width(text, surface.width)
            surface.draw_text_rgb(
                0, 0, text, fg=palette.DEFAULT_FG, bg=palette.DEFAULT_BG
            )
            # Draw block cursor (reverse video) over the character at cursor.
            if cursor_abs < surface.width:
                if cursor < len(value):
                    ch = value[cursor]
                else:
                    ch = " "
                surface.draw_text_rgb(
                    0, cursor_abs, ch, fg=palette.DEFAULT_BG, bg=palette.DEFAULT_FG
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
