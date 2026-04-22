# -*- coding: utf-8 -*-
"""
Module: pigit/termui/event_loop.py
Description: Full-screen TUI main loop (``AppEventLoop``); runs inside :class:`~pigit.termui.session.Session`.
Author: Zev
Date: 2026-03-29
"""

from __future__ import annotations

import logging
import subprocess
from typing import TYPE_CHECKING, Literal, Optional

from ._bindings import BindingsList, resolve_key_handlers_merged
from ._component_base import Component
from ._renderer_context import (
    set_renderer,
    reset_renderer,
    get_renderer,
)
from ._session import Session
from .keys import is_mouse_event

if TYPE_CHECKING:
    from .input_terminal import InputTerminal

_logger = logging.getLogger(__name__)

KeyDispatchOutcome = Literal[
    "binding",
    "resize",
    "child",
    "overlay",
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
        result_message: Optional[str] = None,
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

    BINDINGS: Optional[BindingsList] = None

    def __init__(
        self,
        child: Component,
        input_takeover: bool = False,
        input_handle: Optional["InputTerminal"] = None,
        real_time: bool = True,
        alt: bool = True,
    ) -> None:
        self._child = child
        self._real_time = real_time

        self._input_takeover = input_takeover

        if input_handle is None:
            from pigit.termui.input_bridge import TermuiInputBridge

            input_handle = TermuiInputBridge()
        self._input_handle = input_handle

        self._alt = alt

        self._key_handlers = resolve_key_handlers_merged(
            self, type(self), self.BINDINGS
        )

    def after_start(self):
        """Hook invoked after the loop is ready (subclasses may override)."""

    def before_dispatch_key(self, key: str) -> None:
        """Hook before dispatching a string semantic key (subclasses may override)."""

    def after_dispatch_key(self, key: str, outcome: KeyDispatchOutcome) -> None:
        """Hook after dispatching a string key; ``outcome`` matches the branch taken."""

    def clear_screen(self) -> None:
        renderer = get_renderer()
        if renderer is not None:
            renderer.clear_screen()

    def get_term_size(self):
        from shutil import get_terminal_size

        return get_terminal_size()

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
        from pigit.termui._surface import Surface

        cols, rows = self._size
        surface = Surface(cols, rows)
        self._child._render_surface(surface)
        renderer = get_renderer()
        if renderer is not None:
            renderer.render_surface(surface)

    def set_input_timeouts(self, timeout: float) -> None:
        self._input_handle.set_input_timeouts(timeout)

    def _loop(self) -> None:
        while True:
            input_key = self._input_handle.get_input()
            if not input_key or not input_key[0]:
                if self._real_time:
                    self.render()
                continue
            first = input_key[0][0]
            if isinstance(first, str):
                outcome = self._dispatch_semantic_string(first)
                self.after_dispatch_key(first, outcome)
                continue
            if is_mouse_event(first):
                continue

    def _dispatch_semantic_string(self, key: str) -> KeyDispatchOutcome:
        self.before_dispatch_key(key)
        if key == "window resize":
            self.resize()
            return "resize"
        if self._child.has_overlay_open():
            self._child._handle_event(key)
            self.render()
            return "overlay"
        handler = self._key_handlers.get(key)
        if handler is not None:
            handler()
            self.render()
            return "binding"
        self._child._handle_event(key)
        self.render()
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
            logging.getLogger().exception(
                "AppEventLoop: unhandled exception in main loop: %s", e
            )

    def run(self) -> None:
        with Session(alt_screen=self._alt) as session:
            self._session = session
            token = set_renderer(session.renderer)
            try:
                self._run_impl()
            finally:
                reset_renderer(token)
                self._session = None

    def exec_external(
        self,
        cmd: list[str],
        cwd: Optional[str] = None,
    ) -> "subprocess.CompletedProcess[str]":
        """Suspend TUI, run an external command, then resume TUI and redraw.

        Args:
            cmd: Command argument list (e.g. ["git", "commit"]).
            cwd: Working directory for the command.

        Returns:
            subprocess.CompletedProcess with returncode and other fields.

        Raises:
            RuntimeError: If called outside run() lifecycle.
        """
        session = getattr(self, "_session", None)
        if session is None:
            raise RuntimeError("Session not available; call only inside run().")

        session.suspend()
        result: "subprocess.CompletedProcess[str]"
        try:
            result = subprocess.run(cmd, cwd=cwd, stdin=None, stdout=None, stderr=None)
        finally:
            try:
                session.resume()
            except Exception:
                _logger.exception(
                    "Session.resume() failed; terminal may be in bad state"
                )
                raise
            self.resize()
        return result

    def quit(
        self,
        msg: str = "Quit",
        *,
        exit_code: int = 0,
        result_message: Optional[str] = None,
    ) -> None:
        raise ExitEventLoop(msg, exit_code=exit_code, result_message=result_message)
