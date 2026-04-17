# -*- coding: utf-8 -*-
"""
Module: pigit/termui/application.py
Description: Application facade that composes a root component tree and an event loop.
Author: Zev
Date: 2026-04-17
"""

from __future__ import annotations

from typing import Optional

from pigit.termui.bindings import resolve_key_handlers_merged
from pigit.termui.components import Component
from pigit.termui.event_loop import AppEventLoop


class _ApplicationEventLoop(AppEventLoop):
    """Bridge that delegates after_start and app-level bindings to Application.

    Binding precedence when no overlay is open: App bindings > Loop bindings > Child tree.
    When an overlay is open, keys are routed exclusively to the overlay stack.
    """

    def __init__(self, root: Component, app: "Application", **kwargs):
        super().__init__(root, **kwargs)
        self._app = app
        self._app_key_handlers = getattr(app, "_key_handlers", {})

    def after_start(self):
        self._app.after_start()

    def _dispatch_while_overlay_closed(self, key: str):
        handler = self._app_key_handlers.get(key)
        if handler is not None:
            handler()
            self.render()
            return "binding"
        return super()._dispatch_while_overlay_closed(key)


class Application:
    """
    High-level facade: subclasses implement build_root() and optional app-level bindings.
    """

    BINDINGS = None

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

    def run(self) -> None:
        """Build body, wrap in ComponentRoot, create loop, and start TUI."""
        body = self.build_root()
        from pigit.termui.root import ComponentRoot

        self._root = root = ComponentRoot(body)
        self._loop = _ApplicationEventLoop(root, self, **self._loop_kwargs)
        self.setup_root(root)
        self._loop.run()
