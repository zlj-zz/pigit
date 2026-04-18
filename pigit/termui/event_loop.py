# -*- coding: utf-8 -*-
"""
Module: pigit/termui/event_loop.py
Description: Full-screen TUI main loop (``AppEventLoop``); runs inside :class:`~pigit.termui.session.Session`.
Author: Zev
Date: 2026-03-29
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Literal, Optional

from pigit.termui._bindings import BindingsList, resolve_key_handlers_merged
from pigit.termui._component_base import Component
from pigit.termui.keys import is_mouse_event
from pigit.termui._renderer import Renderer
from pigit.termui._session import Session

if TYPE_CHECKING:
    from pigit.termui.input_terminal import InputTerminal


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
        self._renderer: Optional[Renderer] = None

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

    def _bind_renderer_tree(self, component: Component, renderer: Renderer) -> None:
        """Attach one shared :class:`Renderer` to the whole component tree."""

        component._renderer = renderer
        children = getattr(component, "children", None)
        if children:
            for child in children.values():
                self._bind_renderer_tree(child, renderer)

    def after_start(self):
        """Hook invoked after the loop is ready (subclasses may override)."""

    def before_dispatch_key(self, key: str) -> None:
        """Hook before dispatching a string semantic key (subclasses may override)."""

    def after_dispatch_key(self, key: str, outcome: KeyDispatchOutcome) -> None:
        """Hook after dispatching a string key; ``outcome`` matches the branch taken."""

    def clear_screen(self) -> None:
        if self._renderer is not None:
            self._renderer.clear_screen()

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
        if self._renderer is not None:
            self._renderer.clear_cache()
        self.render()

    def render(self) -> None:
        from pigit.termui._surface import Surface

        cols, rows = self._size
        surface = Surface(cols, rows)
        self._child._render_surface(surface)
        if self._renderer is not None:
            self._renderer.render_surface(surface)

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
        except ExitEventLoop as e:
            self.stop()
            logging.getLogger().debug("AppEventLoop exit: %s", e)
        except (KeyboardInterrupt, EOFError):
            self.stop()
        except Exception as e:
            self.stop()
            logging.getLogger().exception(
                "AppEventLoop: unhandled exception in main loop: %s", e
            )

    def run(self) -> None:
        with Session(alt_screen=self._alt) as session:
            self._renderer = session.renderer
            self._bind_renderer_tree(self._child, session.renderer)
            self._run_impl()

    def quit(
        self,
        msg: str = "Quit",
        *,
        exit_code: int = 0,
        result_message: Optional[str] = None,
    ) -> None:
        raise ExitEventLoop(msg, exit_code=exit_code, result_message=result_message)
