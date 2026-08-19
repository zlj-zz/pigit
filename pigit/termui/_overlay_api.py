"""
Module: pigit/termui/_overlay_api.py
Description: High-level overlay and convenience APIs that operate implicitly
    within the current RuntimeContext.
Author: Zev
Date: 2026-06-10
"""

from __future__ import annotations

import logging
import subprocess
from typing import TYPE_CHECKING, Literal, TypeVar
from collections.abc import Callable, Sequence

_R = TypeVar("_R")

from ._feedback import FeedbackKind, style_for
from ._layer import LayerKind
from . import palette
from .reactive import Signal
from .types import ToastPosition
from ._runtime_context import (
    get_overlay_host,
    get_renderer,
    get_session,
    layer_pop,
    layer_push,
    layer_top,
    request_render,
)

if TYPE_CHECKING:
    from ._component import Component
    from ._segment import Segment
    from .widgets import Sheet, Toast

_logger = logging.getLogger(__name__)

# Module-level badge signal (preserved from _runtime_context)
_badge_signal: Signal[str | None] = Signal(None)


def _with_host(fn: Callable[..., _R]) -> _R | None:
    """Call ``fn(host)`` if an overlay host is active; return ``None`` otherwise.

    Used internally to collapse the repeated ``host = get_overlay_host();
    if host is not None: ...`` guard pattern.
    """
    host = get_overlay_host()
    if host is None:
        return None
    return fn(host)


def exec_external(
    cmd: list[str],
    cwd: str | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess:
    """Suspend TUI, run an external command, then resume TUI and redraw.

    Works from anywhere inside a Session context.

    Stops the keyboard reader before handing the TTY to the child so OSC/DSR
    replies (e.g. Neovim background-color detection) are not consumed by
    pigit's input thread.

    Note: stdout and stderr are not captured because the command inherits
    the terminal directly. Use the return code to check success/failure.

    Args:
        cmd: Command argv (no shell).
        cwd: Working directory.
        env: Environment. When given, it REPLACES the current environment
            (merge with ``os.environ`` if inheriting is needed).
    """
    session = get_session()
    if session is None:
        raise RuntimeError("No active TUI session; call only inside Session context.")

    host = get_overlay_host()
    loop = getattr(host, "_event_loop", None) if host is not None else None
    input_handle = getattr(loop, "_input_handle", None) if loop is not None else None

    if input_handle is not None:
        input_handle.stop()
    session.suspend()
    try:
        result = subprocess.run(
            cmd, cwd=cwd, env=env, stdin=None, stdout=None, stderr=None
        )
    finally:
        resume_error = None
        try:
            session.resume()
        except Exception as e:
            _logger.exception("Session.resume() failed; terminal may be in bad state")
            resume_error = e
        if input_handle is not None:
            try:
                input_handle.start()
            except Exception:
                _logger.exception("Failed to restart keyboard input after external cmd")
        renderer = get_renderer()
        if renderer is not None:
            renderer.clear_cache()
        if resume_error is not None:
            raise resume_error
    return result


def show_toast(
    message: str = "",
    *,
    segments: Sequence[Segment] | None = None,
    duration: float = 2.0,
    position: ToastPosition | None = None,
    kind: FeedbackKind | None = None,
) -> Toast | None:
    """Display a transient toast notification via the current overlay host.

    ``kind`` selects the semantic level (info/success/warning/error); ``None``
    is the neutral level with no glyph or semantic color. ``segments``, when
    given, overrides ``kind`` (the glyph/color are skipped)."""
    from .widgets import Toast

    host = get_overlay_host()
    if host is None:
        return None

    # Dismiss existing toast first
    existing = layer_top(LayerKind.TOAST)
    if existing is not None:
        existing.hide()
        layer_pop(LayerKind.TOAST)

    if position is None:
        position = ToastPosition.TOP_RIGHT

    # segments (e.g. show_spinner) render verbatim; suppress kind glyph/color.
    if segments is not None:
        kind = None

    toast = Toast(
        message, segments=segments, duration=duration, position=position, kind=kind
    )
    toast._event_loop = getattr(host, "_event_loop", None)
    toast.resize(host.size)
    layer_push(LayerKind.TOAST, toast)
    request_render()
    return toast


def show_sheet(
    child: Component,
    height: int = 8,
    show_border: bool = False,
    *,
    edge: Literal["top", "bottom"] = "bottom",
    bg: tuple[int, int, int] | None = palette.DEFAULT_BG,
) -> Sheet | None:
    """Display a sheet via the current overlay host."""
    sheet = _with_host(
        lambda h: h.show_sheet(child, height, show_border=show_border, edge=edge, bg=bg)
    )
    if sheet is not None:
        request_render()
    return sheet


def dismiss_sheet() -> None:
    """Dismiss the current bottom sheet via the overlay host."""
    host = get_overlay_host()
    if host is not None:
        host.dismiss_sheet()


def get_badge_signal() -> Signal[str | None]:
    """Return the global badge-change signal for reactive header binding."""
    return _badge_signal


def show_badge(
    text: str,
    duration: float | None = None,
    bg: tuple[int, int, int] | None = None,
    fg: tuple[int, int, int] | None = None,
    kind: FeedbackKind | None = None,
) -> None:
    """Show a badge on the overlay host.

    ``kind`` sets the foreground from the semantic palette unless ``fg`` is
    given explicitly."""
    if kind is not None and fg is None:
        _style = style_for(kind)
        if _style is not None:
            fg = _style.fg
    host = get_overlay_host()
    if host is None:
        return
    host.show_badge(text, duration=duration, bg=bg, fg=fg)
    if _badge_signal.value != text:
        _badge_signal.set(text)
    request_render()


def get_badge() -> tuple[
    str | None,
    tuple[int, int, int] | None,
    tuple[int, int, int] | None,
]:
    """Get current badge state from the overlay host.

    Returns:
        Tuple of (badge_text, badge_bg, badge_fg). All None if no badge
        or no host is active.
    """
    host = get_overlay_host()
    if host is None:
        return None, None, None
    return host.badge_text, host.badge_bg, host.badge_fg


def show_spinner(message: str) -> Toast | None:
    """Display a persistent spinner toast (duration=3600s), replacing any current toast.

    The message is prefixed with ``»`` and suffixed with ``…`` automatically.
    """
    from ._segment import Segment

    return show_toast(
        "",
        segments=[Segment(f"» {message}…")],
        duration=3600.0,
        position=ToastPosition.BOTTOM_LEFT,
    )


def dismiss_toast() -> None:
    """Dismiss the current toast, if any."""
    existing = layer_top(LayerKind.TOAST)
    if existing is not None:
        existing.hide()
        layer_pop(LayerKind.TOAST)


def hide_spinner() -> None:
    """Dismiss the current spinner toast."""
    dismiss_toast()
