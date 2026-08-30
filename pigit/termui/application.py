"""
Module: pigit/termui/application.py
Description: Application facade that composes a root component tree and an event loop.
Author: Zev
Date: 2026-08-20
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypedDict, Unpack

from .bindings import (
    BindingsList,
    ExecutableBinding,
    derive_executable_bindings,
    derive_help_entries,
    resolve_instance_bindings,
)
from .component import Component
from .root import ComponentRoot
from .event_bus import EventBus
from .event_loop import AppEventLoop, ExitEventLoop
from .types import EventType
from . import keys

if TYPE_CHECKING:
    from .input import InputTerminal


class LoopKwargs(TypedDict, total=False):
    """Keyword arguments forwarded to :class:`~pigit.termui.event_loop.AppEventLoop`."""

    input_takeover: bool
    input_handle: InputTerminal
    real_time: bool
    alt: bool


class Application:
    """
    High-level facade: subclasses implement build_root() and optional app-level bindings.

    Bindings and ``handle_key`` are installed on :class:`ComponentRoot`, which
    is the single keyboard entry for :class:`AppEventLoop`.
    """

    BINDINGS: BindingsList | None = None

    # Declarative lifecycle configuration (override in subclass)
    min_terminal_size: tuple[int, int] = (0, 0)
    help_popup_class: type[Component] | None = None
    help_binding: str = "?"

    def __init__(self, **loop_kwargs: Unpack[LoopKwargs]) -> None:
        self._loop: AppEventLoop | None = None
        self._root: ComponentRoot | None = None
        self._loop_kwargs = loop_kwargs
        self._action_bindings, self._key_handlers = resolve_instance_bindings(self)
        self._help_popup: Any = None
        self._event_bus = EventBus()

    def get_executable_bindings(self):
        """Derive app-level executable help rows from ``@bind_action``."""
        return derive_executable_bindings(self._action_bindings, self)

    def get_help_entries(self) -> list[tuple[str, str]]:
        """Derive app-level (universal) help entries from ``@bind_action``."""
        return derive_help_entries(self._action_bindings, self)

    def get_help_groups(self) -> list[tuple[str, list[ExecutableBinding]]]:
        """Return grouped help entries for the help popup.

        Default: a single ``Global`` group when universal entries exist.

        Returns:
            List of ``(group_title, entries)`` tuples.
        """
        universal = self.get_executable_bindings()
        if universal:
            return [("Global", universal)]
        return []

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

    def on_exit(self) -> None:
        """Lifecycle hook invoked before ``root.destroy()`` on teardown.

        Override to stop observers, cancel timers, or release app resources.
        The root is still available as ``self._root`` when this runs.
        """

    def resize(self, size: tuple[int, int]) -> None:
        """Adjust layout before the loop resizes the component tree.

        Override for app-level layout (column widths, stash height). The
        event loop always resizes ``ComponentRoot`` after this returns.
        """

    def on_event(self, action: EventType, **data) -> bool:
        """Override to handle events bubbled from component tree.

        Return True to stop bubbling, False to let it continue up.
        """
        return False

    def handle_key(self, key: str) -> bool:
        """Optional app-level key hook after overlay/bindings.

        Return True when the key was handled.
        """
        return False

    def _auto_setup_root(self, root: ComponentRoot) -> None:
        """Inject framework-level setup before user ``setup_root`` runs."""
        if self.help_popup_class is not None:
            from .widgets import Popup

            help_panel = self.help_popup_class()
            self._help_popup = Popup(help_panel, exit_key=keys.KEY_ESC)

    def _on_loop_after_start(self) -> None:
        """Run user ``after_start`` then framework terminal-size checks."""
        self.after_start()
        self._auto_after_start()

    def _auto_after_start(self) -> None:
        """Inject framework-level checks after user ``after_start`` runs."""
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

            def _app_handle_key(key: str) -> bool:
                return self.handle_key(key)

            self._root = root = ComponentRoot(
                body,
                runtime.registry,
                event_bus=self._event_bus,
                key_handlers=self._key_handlers,
                handle_key=_app_handle_key,
            )
            runtime.overlay_host = root
            runtime.focus_manager = root._focus_manager
            root._app_on_event = self.on_event
            self._loop = AppEventLoop(
                root,
                on_after_start=self._on_loop_after_start,
                on_before_resize=self.resize,
                **self._loop_kwargs,
            )
            root._event_loop = self._loop
            self._auto_setup_root(root)
            self.setup_root(root)
            root.mount()
            self._loop.run()
        finally:
            try:
                if self._root is not None:
                    self.on_exit()
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
