# -*- coding: utf-8 -*-
"""
Module: pigit/termui/event_loop.py
Description: Full-screen TUI main loop (``AppEventLoop``); pairs with :class:`~pigit.termui.session.Session` when using ``KeyboardInput``.
Author: Project Team
Date: 2026-03-27
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, List, Optional, Tuple

from pigit.termui.components import Component
from pigit.termui.render import Renderer, renderer_for_stdout

if TYPE_CHECKING:
    from pigit.termui.input_terminal import InputTerminal


class ExitEventLoop(Exception):
    """Raised to exit the current event loop."""


class AppEventLoop:
    """
    Application-level keyboard loop over a component tree.

    ``_renderer`` is the single drawing surface: created from :class:`~pigit.termui.session.Session`
    when ``use_termui_keyboard=True``, else bound to ``sys.stdout`` for legacy ``PosixInput`` runs.
    """

    BINDINGS: Optional[List[Tuple[str, str]]] = None

    def __init__(
        self,
        child: Component,
        input_takeover: bool = False,
        input_handle: Optional["InputTerminal"] = None,
        real_time: bool = False,
        alt: bool = True,
        use_termui_keyboard: bool = False,
    ) -> None:
        self._renderer: Optional[Renderer] = None

        self._child = child
        self._real_time = real_time

        self._input_takeover = input_takeover
        self._session_wrap = False
        if not input_handle:
            if use_termui_keyboard:
                from pigit.termui.tui_input_bridge import TermuiInputBridge

                input_handle = TermuiInputBridge()
                self._session_wrap = True
            else:
                from pigit.termui.legacy_input import PosixInput, is_mouse_event

                input_handle = PosixInput()
                self.is_mouse_event = is_mouse_event
        self._input_handle = input_handle

        self._alt = alt

        self._event_map = {}
        if self.BINDINGS is not None:
            for ev in self.BINDINGS:
                self._event_map[ev[0]] = ev[1]

    def _bind_renderer_tree(self, component: Component, renderer: Renderer) -> None:
        """Attach one shared :class:`Renderer` to the whole component tree."""

        component._renderer = renderer
        children = getattr(component, "children", None)
        if not children:
            return
        for child in children.values():
            self._bind_renderer_tree(child, renderer)

    def after_start(self):
        """Hook invoked after the loop is ready (subclasses may override)."""

    def to_alt_screen(self) -> None:
        if self._renderer is None:
            return
        self._renderer.write("\033[?1049h\033[?25l")
        self._renderer.flush()

    def to_normal_screen(self) -> None:
        if self._renderer is None:
            return
        self._renderer.write("\033[?1049l\033[?25h")
        self._renderer.flush()

    def clear_screen(self) -> None:
        if self._renderer is not None:
            self._renderer.clear_screen()

    def get_term_size(self):
        from shutil import get_terminal_size

        return get_terminal_size()

    def start(self):
        if self._session_wrap:
            self.resize()
            self.after_start()
            return

        if self._alt:
            self.to_alt_screen()

        if self._input_takeover and self._input_handle is not None:
            self._input_handle.start()

        self.resize()
        self.after_start()

    def stop(self):
        if self._session_wrap:
            return

        if self._alt:
            self.to_normal_screen()

        if self._input_takeover and self._input_handle is not None:
            self._input_handle.stop()

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_value, exc_tb):
        self.stop()

    def resize(self) -> None:
        """Refresh terminal size, propagate to the root component, and redraw."""

        self._size = self.get_term_size()
        self._child.resize(self._size)
        self.render()

    def render(self) -> None:
        self.clear_screen()
        self._child._render()

    def set_input_timeouts(self, timeout: float) -> None:
        self._input_handle.set_input_timeouts(timeout)

    def _loop(self) -> None:
        while True:
            if (input_key := self._input_handle.get_input()) and input_key[0]:
                first_one: str = input_key[0][0]

                tg_name = self._event_map.get(first_one)
                tg_fn = None if tg_name is None else getattr(self, tg_name, None)

                if callable(tg_fn):
                    tg_fn()
                elif first_one == "window resize":
                    self.resize()
                elif hasattr(self, "is_mouse_event") and self.is_mouse_event(first_one):
                    pass
                else:
                    self._child._handle_event(first_one)
            elif self._real_time:
                self._child._render()

    def _run_impl(self) -> None:
        try:
            self.start()
            self._loop()
        except (ExitEventLoop, KeyboardInterrupt, EOFError) as e:
            self.stop()
            print(e, e.__traceback__)
        except Exception as e:
            self.stop()
            print(e, e.__traceback__)

    def run(self) -> None:
        if self._session_wrap:
            from pigit.termui.session import Session

            with Session(alt_screen=self._alt) as session:
                self._renderer = session.renderer
                self._bind_renderer_tree(self._child, session.renderer)
                self._run_impl()
        else:
            self._renderer = renderer_for_stdout(sys.stdout)
            self._bind_renderer_tree(self._child, self._renderer)
            self._run_impl()

    def quit(self, msg: str = "Quit") -> None:
        raise ExitEventLoop(msg)
