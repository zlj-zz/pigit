# -*- coding: utf-8 -*-
"""
Module: pigit/termui/_application.py
Description: Application facade that composes a root component tree and an event loop.
Author: Zev
Date: 2026-04-19
"""

from __future__ import annotations

import logging
from typing import Optional, TYPE_CHECKING

from pigit.termui._bindings import BindingsList, resolve_key_handlers_merged
from pigit.termui._component_base import Component
from pigit.termui._root import ComponentRoot
from pigit.termui.event_loop import AppEventLoop, ExitEventLoop

if TYPE_CHECKING:
    import subprocess

_logger = logging.getLogger(__name__)


class _ApplicationEventLoop(AppEventLoop):
    """Bridge that delegates after_start and app-level bindings to Application.

    Binding precedence when no overlay is open: App bindings > Loop bindings > Child tree.
    When an overlay is open, keys are routed exclusively to the overlay stack.
    """

    def __init__(self, root: Component, app: "Application", **kwargs):
        super().__init__(root, **kwargs)
        self._app = app
        self._app_key_handlers = getattr(app, "_key_handlers", {})
        self._app_on_key = getattr(app, "on_key", None)

    def after_start(self):
        """Delegate the after-start hook to the Application instance."""
        self._app.after_start()

    def _dispatch_semantic_string(self, key: str):
        self.before_dispatch_key(key)
        if key == "window resize":
            self.resize()
            return "resize"

        handler = self._app_key_handlers.get(key)
        if handler is not None:
            try:
                handler()
            except ExitEventLoop:
                raise
            except Exception:
                _logger.exception("App binding for '%s' failed", key)
            self.render()
            return "binding"

        if self._app_on_key is not None:
            try:
                self._app_on_key(key)
            except ExitEventLoop:
                raise
            except Exception:
                _logger.exception("App on_key for '%s' failed", key)
            self.render()
            return "app"

        return super()._dispatch_semantic_string(key)


class Application:
    """
    High-level facade: subclasses implement build_root() and optional app-level bindings.
    """

    BINDINGS: Optional[BindingsList] = None

    def __init__(self, **loop_kwargs) -> None:
        self._loop: Optional[AppEventLoop] = None
        self._loop_kwargs = loop_kwargs
        self._key_handlers = resolve_key_handlers_merged(
            self, type(self), self.BINDINGS
        )

    def build_root(self) -> Component:
        """Return the user body component (usually a TabView)."""
        raise NotImplementedError("Subclasses must implement build_root().")

    def setup_root(self, root) -> None:
        """
        Hook after ComponentRoot is created but before loop starts.
        Attach overlays (Popup, AlertDialog) here.
        """
        pass

    def after_start(self) -> None:
        """Lifecycle hook invoked after the loop is ready."""
        pass

    def resize(self, size: tuple[int, int]) -> None:
        """Manually trigger resize on the root component tree."""
        if self._root is not None:
            self._root.resize(size)

    def _run_body(self) -> None:
        """Assemble root, create loop, and start TUI. Does NOT catch ExitEventLoop."""
        body = self.build_root()
        self._root = root = ComponentRoot(body)
        self._loop = _ApplicationEventLoop(root, self, **self._loop_kwargs)
        self.setup_root(root)
        try:
            self._loop.run()
        finally:
            root.destroy()

    def run_external_process(
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
        if self._loop is None:
            raise RuntimeError("Application not running.")
        return self._loop.exec_external(cmd, cwd=cwd)

    def run(self) -> None:
        """Long-lived TUI entry. Swallows ExitEventLoop for backward compatibility.

        ``exit_code`` and ``result_message`` from the exception are intentionally
        discarded. Use :meth:`run_with_result` if you need the exit tuple.
        """
        try:
            self._run_body()
        except ExitEventLoop:
            pass

    def run_with_result(self) -> tuple[int, Optional[str]]:
        """Short-lived TUI entry returning (exit_code, message).

        Used by pickers and other one-shot interactive flows.
        """
        from pigit.termui._picker import PICK_EXIT_CTRL_C

        try:
            self._run_body()
        except ExitEventLoop as e:
            return e.exit_code, e.result_message
        except KeyboardInterrupt:
            return PICK_EXIT_CTRL_C, None
        except EOFError:
            return 0, None  # input exhausted — graceful exit
        return 0, None
