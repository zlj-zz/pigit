"""
Module: pigit/termui/_application.py
Description: Application facade that composes a root component tree and an event loop.
Author: Zev
Date: 2026-04-19
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, TypedDict

if TYPE_CHECKING:
    from typing_extensions import Unpack

from ._bindings import BindingsList, resolve_key_handlers_merged
from ._component import Component
from ._root import ComponentRoot
from .event_loop import AppEventLoop, ExitEventLoop, KeyDispatchOutcome
from .types import ActionEventType, OverlayDispatchResult
from . import keys

if TYPE_CHECKING:
    from .input import InputTerminal

_logger = logging.getLogger(__name__)


class LoopKwargs(TypedDict, total=False):
    """Keyword arguments forwarded to :class:`~pigit.termui.event_loop.AppEventLoop`."""

    input_takeover: bool
    input_handle: InputTerminal
    real_time: bool
    alt: bool


class _ApplicationEventLoop(AppEventLoop):
    """Bridge that delegates after_start and app-level bindings to Application.

    Binding precedence: App bindings > Loop bindings > Component tree.
    ComponentRoot routes keys to the overlay stack or leaf internally.
    """

    _child: ComponentRoot

    def __init__(self, root: ComponentRoot, app: Application, **kwargs):
        super().__init__(root, **kwargs)
        self._app = app
        self._app_key_handlers = getattr(app, "_key_handlers", {})
        self._app_on_key = getattr(app, "on_key", None)

    def after_start(self):
        """Delegate the after-start hook to the Application instance."""
        self._app.after_start()
        self._app._auto_after_start()

    def resize(self) -> None:
        """Propagate resize to the Application before the component tree."""
        self._app.resize(self.get_term_size())
        super().resize()

    def _dispatch_semantic_string(self, key: str) -> KeyDispatchOutcome:
        self.before_dispatch_key(key)
        if key == "window resize":
            self.resize()
            return "resize"

        # When an overlay is open, give it first dibs.  If the overlay
        # consumes the key (anything other than DROPPED_UNBOUND) we stop
        # here so that Sheet/Modal interactions are not hijacked by global
        # shortcuts (e.g. "2" switching tabs while typing in a commit).
        if self._child.has_overlay_open():
            result = self._child.try_dispatch_overlay(key)
            if result != OverlayDispatchResult.DROPPED_UNBOUND:
                self._child._focus_manager.sync_focus_to_overlay_or_leaf()
                self.request_render()
                return "child"
            # Overlay explicitly dropped the key — fall through to app bindings.

        handler = self._app_key_handlers.get(key)
        if handler is not None:
            self._run_app_handler(handler, key, "App binding for '%s' failed")
            return "binding"

        app_on_key = self._app_on_key
        if app_on_key is not None:
            self._run_app_handler(
                lambda: app_on_key(key), key, "App on_key for '%s' failed"
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
        self._child.sync_focus_after_app_binding(overlay_was_open)
        self.render()


class Application:
    """
    High-level facade: subclasses implement build_root() and optional app-level bindings.
    """

    BINDINGS: BindingsList | None = None

    # Declarative lifecycle configuration (override in subclass)
    min_terminal_size: tuple[int, int] | None = None
    input_timeouts: float = 0.0625
    help_popup_class: type[Component] | None = None
    help_binding: str = "?"

    def __init__(self, **loop_kwargs: Unpack[LoopKwargs]) -> None:
        self._loop: AppEventLoop | None = None
        self._root: ComponentRoot | None = None
        self._loop_kwargs = loop_kwargs
        self._key_handlers = resolve_key_handlers_merged(
            self, type(self), self.BINDINGS
        )
        self._help_popup: Any = None

    def build_root(self) -> Component:
        """Return the user body component (usually a TabView)."""
        raise NotImplementedError("Subclasses must implement build_root().")

    def setup_root(self, root) -> None:
        """
        Hook after ComponentRoot is created but before loop starts.
        Attach overlays (Popup, AlertDialog) here.
        """

    def after_start(self) -> None:
        """Lifecycle hook invoked after the loop is ready."""

    def resize(self, size: tuple[int, int]) -> None:
        """Manually trigger resize on the root component tree."""
        if self._root is not None:
            self._root.resize(size)

    def on_event(self, action: ActionEventType, **data) -> bool:
        """Override to handle events bubbled from component tree.

        Return True to stop bubbling, False to let it continue up.
        """
        return False

    def _auto_setup_root(self, root: ComponentRoot) -> None:
        """Inject framework-level setup before user ``setup_root`` runs."""
        if self.help_popup_class is not None:
            from .widgets import Popup

            help_panel = self.help_popup_class()
            self._help_popup = Popup(help_panel, exit_key=keys.KEY_ESC)
            # Binding registered in _ApplicationEventLoop via app bindings

    def _auto_after_start(self) -> None:
        """Inject framework-level checks after user ``after_start`` runs."""
        if self.min_terminal_size is not None:
            from .tty_io import terminal_size

            cols, rows = terminal_size()
            min_cols, min_rows = self.min_terminal_size
            if cols < min_cols or rows < min_rows:
                self.quit(
                    exit_code=1,
                    result_message=f"Terminal too small (need {min_cols}x{min_rows})",
                )

    def quit(self, *, exit_code: int = 0, result_message: str | None = None) -> None:
        """Request graceful exit from the event loop."""
        raise ExitEventLoop("quit", exit_code=exit_code, result_message=result_message)

    def _run_body(self) -> None:
        """Assemble root, create loop, and start TUI. Does NOT catch ExitEventLoop."""
        from ._runtime_context import RuntimeContext, _runtime_ctx

        runtime = RuntimeContext()
        token = _runtime_ctx.set(runtime)
        try:
            body = self.build_root()
            self._root = root = ComponentRoot(body, runtime.registry)
            runtime.overlay_host = root
            runtime.focus_manager = root._focus_manager
            root._app_on_event = self.on_event
            self._loop = _ApplicationEventLoop(root, self, **self._loop_kwargs)
            self._loop.set_input_timeouts(self.input_timeouts)
            self._auto_setup_root(root)
            self.setup_root(root)
            self._loop.run()
        finally:
            if self._root is not None:
                self._root.destroy()
                self._root = None
            _runtime_ctx.reset(token)

    def run(self) -> None:
        """Long-lived TUI entry. Swallows ExitEventLoop for backward compatibility.

        ``exit_code`` and ``result_message`` from the exception are intentionally
        discarded. Use :meth:`run_with_result` if you need the exit tuple.
        """
        try:
            self._run_body()
        except ExitEventLoop:
            pass

    def run_with_result(self) -> tuple[int, str | None]:
        """Short-lived TUI entry returning (exit_code, message).

        Used by pickers and other one-shot interactive flows.
        """
        try:
            self._run_body()
        except ExitEventLoop as e:
            return e.exit_code, e.result_message
        except KeyboardInterrupt:
            return 130, None
        except EOFError:
            return 0, None  # input exhausted — graceful exit
        return 0, None
