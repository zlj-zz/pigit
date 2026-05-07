# -*- coding: utf-8 -*-
"""
Module: pigit/termui/_application.py
Description: Application facade that composes a root component tree and an event loop.
Author: Zev
Date: 2026-04-19
"""

from __future__ import annotations

import logging
from typing import Optional, TYPE_CHECKING, TypedDict

if TYPE_CHECKING:
    from typing_extensions import Unpack

from ._bindings import BindingsList, resolve_key_handlers_merged
from ._component_base import Component, _set_focus_chain
from ._root import ComponentRoot
from .event_loop import AppEventLoop, ExitEventLoop
from .types import ActionEventType

if TYPE_CHECKING:
    from .input_bridge import InputTerminal

_logger = logging.getLogger(__name__)


class LoopKwargs(TypedDict, total=False):
    """Keyword arguments forwarded to :class:`~pigit.termui.event_loop.AppEventLoop`."""

    input_takeover: bool
    input_handle: "InputTerminal"
    real_time: bool
    alt: bool


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
            self._run_app_handler(handler, key, "App binding for '%s' failed")
            return "binding"

        if self._app_on_key is not None:
            self._run_app_handler(
                lambda: self._app_on_key(key), key, "App on_key for '%s' failed"
            )
            return "app"

        return super()._dispatch_semantic_string(key)

    def _run_app_handler(self, handler, key: str, log_fmt: str) -> None:
        overlay_was_open = self._child.has_overlay_open()
        try:
            handler()
        except ExitEventLoop:
            raise
        except Exception:
            _logger.exception(log_fmt, key)
        if overlay_was_open and not self._child.has_overlay_open():
            _set_focus_chain(self._child._find_focus_leaf())
        self.render()


class Application:
    """
    High-level facade: subclasses implement build_root() and optional app-level bindings.
    """

    BINDINGS: Optional[BindingsList] = None

    def __init__(self, **loop_kwargs: "Unpack[LoopKwargs]") -> None:
        self._loop: Optional[AppEventLoop] = None
        self._root: Optional[ComponentRoot] = None
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

    def on_event(self, action: ActionEventType, **data) -> bool:
        """Override to handle events bubbled from component tree.

        Return True to stop bubbling, False to let it continue up.
        """
        return False

    def _run_body(self) -> None:
        """Assemble root, create loop, and start TUI. Does NOT catch ExitEventLoop."""
        from ._component_registry import ComponentRegistry, _registry_ctx

        registry = ComponentRegistry()
        token = _registry_ctx.set(registry)
        try:
            body = self.build_root()
            self._root = root = ComponentRoot(body, registry)
            root._app_on_event = self.on_event
            self._loop = _ApplicationEventLoop(root, self, **self._loop_kwargs)
            self.setup_root(root)
            self._loop.run()
        finally:
            if self._root is not None:
                self._root.destroy()
            _registry_ctx.reset(token)

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
        from ._picker import PICK_EXIT_CTRL_C

        try:
            self._run_body()
        except ExitEventLoop as e:
            return e.exit_code, e.result_message
        except KeyboardInterrupt:
            return PICK_EXIT_CTRL_C, None
        except EOFError:
            return 0, None  # input exhausted — graceful exit
        return 0, None
