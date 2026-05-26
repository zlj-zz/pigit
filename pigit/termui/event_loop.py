"""
Module: pigit/termui/event_loop.py
Description: Full-screen TUI main loop (``AppEventLoop``); runs inside :class:`~pigit.termui.session.Session`.
Author: Zev
Date: 2026-03-29
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Literal

from . import keys
from ._async_task import AsyncTask
from ._bindings import BindingsList, resolve_key_handlers_merged
from ._component import Component
from ._runtime_context import get_renderer
from ._session import Session
from .tty_io import terminal_size

if TYPE_CHECKING:
    from .input import InputTerminal

_logger = logging.getLogger(__name__)

KeyDispatchOutcome = Literal[
    "binding",
    "resize",
    "child",
    "app",
]


class ExitEventLoop(Exception):
    """
    Raised to exit the current event loop.

    Pickers attach ``exit_code`` / ``result_message`` for CLI-style
    ``(exit_code, message)`` returns; the main Git TUI uses defaults only.
    """

    def __init__(
        self,
        msg: str = "Quit",
        *,
        exit_code: int = 0,
        result_message: Any | None = None,
    ) -> None:
        super().__init__(msg)
        self.exit_code = exit_code
        self.result_message = result_message


class AppEventLoop:
    """
    Application-level keyboard loop over a component tree.

    ``run()`` always enters :class:`~pigit.termui.session.Session` and binds
    ``session.renderer`` to the whole component tree. When ``input_handle`` is
    omitted, a :class:`~pigit.termui.input_bridge.TermuiInputBridge` over
    :class:`~pigit.termui.input_keyboard.KeyboardInput` is used.
    """

    BINDINGS: BindingsList | None = None

    def __init__(
        self,
        child: Component,
        input_takeover: bool = False,
        input_handle: InputTerminal | None = None,
        real_time: bool = True,
        alt: bool = True,
    ) -> None:
        self._child = child
        self._real_time = real_time

        self._input_takeover = input_takeover

        if input_handle is None:
            from .input import TermuiInputBridge

            input_handle = TermuiInputBridge()
        self._input_handle = input_handle

        self._alt = alt

        self._key_handlers = resolve_key_handlers_merged(
            self, type(self), self.BINDINGS
        )

        self._render_requested = False
        self._surface: Any = None
        self._had_overlay = False

    def request_render(self) -> None:
        """Request a render on the next loop iteration.

        Multiple calls within a single frame are coalesced into one render.
        """
        self._render_requested = True

    def after_start(self):
        """Hook invoked after the loop is ready (subclasses may override)."""

    def before_dispatch_key(self, key: str) -> None:
        """Hook before dispatching a string semantic key (subclasses may override)."""

    def after_dispatch_key(self, key: str, outcome: KeyDispatchOutcome) -> None:
        """Hook after dispatching a string key; ``outcome`` matches the branch taken."""

    def before_mouse_event(self, event: str) -> None:
        """Hook before handling a mouse event (subclasses may override)."""

    def clear_screen(self) -> None:
        """Clear the terminal screen via the current renderer."""
        renderer = get_renderer()
        if renderer is not None:
            renderer.clear_screen()

    def get_term_size(self):
        return terminal_size()

    def start(self):
        """Prepare layout; alternate screen and termios are owned by :class:`Session` inside ``run()``."""

        self.resize()
        self.after_start()

    def stop(self):
        """Terminal restoration is performed by :class:`Session` when ``run()`` exits."""

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_value, exc_tb):
        self.stop()

    def resize(self) -> None:
        """Refresh terminal size, propagate to the root component, and redraw."""

        self._size = self.get_term_size()
        self._child.resize(self._size)
        renderer = get_renderer()
        if renderer is not None:
            renderer.clear_cache()
        self.render()

    def render(self) -> None:
        """Render the component tree to the terminal."""
        from ._surface import Surface

        cols, rows = self._size
        surface = self._surface
        if surface is None or surface.width != cols or surface.height != rows:
            surface = Surface(cols, rows)
            self._surface = surface
        else:
            surface.clear()

        has_overlay = self._child.has_overlay_open()
        if has_overlay != self._had_overlay:
            renderer = get_renderer()
            if renderer is not None:
                renderer.clear_cache()
        self._had_overlay = has_overlay

        self._child._render_surface(surface)
        renderer = get_renderer()
        if renderer is not None:
            renderer.render_surface(surface)

    def set_input_timeouts(self, timeout: float) -> None:
        """Set the input polling timeout on the underlying input handle."""
        self._input_handle.set_input_timeouts(timeout)

    def _loop(self) -> None:
        while True:
            AsyncTask.poll_all()
            if self._render_requested:
                _logger.debug("[RENDER] _loop: render (poll)")
                self._render_requested = False
                self.render()
            input_key = self._input_handle.get_input()
            if not input_key or not input_key[0]:
                if self._render_requested or self._real_time:
                    self._render_requested = False
                    self.render()
                continue
            first = input_key[0][0]
            if isinstance(first, str):
                _logger.debug("[RENDER] _loop: dispatch key=%r", first)
                outcome = self._dispatch_semantic_string(first)
                self.after_dispatch_key(first, outcome)
                if self._render_requested:
                    _logger.debug("[RENDER] _loop: render (after dispatch)")
                    self._render_requested = False
                    self.render()
                continue
            if keys.is_mouse_event(first):
                self.before_mouse_event(first)
                continue

    def _dispatch_semantic_string(self, key: str) -> KeyDispatchOutcome:
        self.before_dispatch_key(key)
        if key == "window resize":
            self.resize()
            return "resize"
        handler = self._key_handlers.get(key)
        if handler is not None:
            try:
                handler()
            except ExitEventLoop:
                raise
            except Exception:
                _logger.exception("Key handler for '%s' failed", key)
            self.request_render()
            return "binding"
        try:
            self._child._handle_event(key)
        except ExitEventLoop:
            raise
        except Exception:
            _logger.exception("Child handler for '%s' failed", key)
        self.request_render()
        return "child"

    def _run_impl(self) -> None:
        try:
            self.start()
            self._loop()
        except ExitEventLoop:
            self.stop()
            raise
        except KeyboardInterrupt:
            self.stop()
            raise
        except EOFError:
            self.stop()
            raise
        except Exception as e:
            self.stop()
            _logger.exception("AppEventLoop: unhandled exception in main loop: %s", e)
            raise

    def run(self) -> None:
        """Enter a Session, bind the renderer, and run the main event loop."""
        from ._runtime_context import RuntimeContext

        with Session(alt_screen=self._alt) as session:
            self._session = session
            runtime = RuntimeContext.current()
            if runtime is not None:
                runtime.session = session
                runtime.renderer = session.renderer
                runtime.render_request = self.request_render
            try:
                self._run_impl()
            finally:
                if runtime is not None:
                    runtime.session = None
                    runtime.renderer = None
                    runtime.render_request = None
                self._session = None

    def quit(
        self,
        msg: str = "Quit",
        *,
        exit_code: int = 0,
        result_message: str | None = None,
    ) -> None:
        """Raise ExitEventLoop to break out of the event loop."""
        raise ExitEventLoop(msg, exit_code=exit_code, result_message=result_message)
