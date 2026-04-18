"""
Event loop tests.

Note on overlay architecture: ComponentMock.has_overlay_open() and
try_dispatch_overlay() simulate the old single-slot host protocol.
In the current LayerStack architecture, these methods are implemented
by ComponentRoot, which delegates to LayerStack for overlay checks,
dispatch, and rendering. ComponentMock remains valid because
ComponentRoot exposes the same backward-compatible interface.
"""

import pytest
from unittest.mock import MagicMock, Mock, patch

from pigit.termui.components import Component
from pigit.termui.tui_input_bridge import TermuiInputBridge
from pigit.termui.event_loop import AppEventLoop, ExitEventLoop
from pigit.termui.input_terminal import InputTerminal

EventLoop = AppEventLoop


class ComponentMock:
    def resize(self, size):
        pass

    def _render_surface(self, surface):
        pass

    def _handle_event(self, event):
        pass

    def has_overlay_open(self):
        return False

    def try_dispatch_overlay(self, key):
        from pigit.termui.overlay_kinds import OverlayDispatchResult

        return OverlayDispatchResult.DROPPED_UNBOUND


@pytest.mark.parametrize(
    "real_time, alt",
    [
        (True, True),
        (False, False),
        (True, False),
        (False, True),
    ],
)
def test_start_stop_does_not_toggle_alt_outside_session(real_time, alt):
    """Alternate screen is owned by ``Session`` inside ``run()``; ``start``/``stop`` are layout hooks."""

    component = ComponentMock()
    event_loop = EventLoop(component, real_time=real_time, alt=alt)
    event_loop.get_term_size = Mock(return_value=(80, 24))
    event_loop.start()
    event_loop.stop()


def test_init_default_input_is_termui_bridge():
    component = ComponentMock()
    loop = EventLoop(component, alt=False)
    assert isinstance(loop._input_handle, TermuiInputBridge)


def test_init_respects_injected_input_handle():
    component = ComponentMock()
    mock_handle = Mock(spec=InputTerminal)
    loop = EventLoop(component, input_handle=mock_handle, alt=False)
    assert loop._input_handle is mock_handle


@pytest.mark.parametrize(
    "exc_factory, expected_stop_calls",
    [
        (lambda: ExitEventLoop("x"), 1),
        (lambda: KeyboardInterrupt(), 1),
        (lambda: EOFError(), 1),
        (lambda: RuntimeError("x"), 1),
    ],
)
@patch("pigit.termui.event_loop.Session")
def test_run_exception_handling(mock_session_cls, exc_factory, expected_stop_calls):
    session_cm = MagicMock()
    session_inner = MagicMock()
    session_inner.renderer = MagicMock()
    session_cm.__enter__.return_value = session_inner
    session_cm.__exit__.return_value = None
    mock_session_cls.return_value = session_cm

    component = ComponentMock()
    event_loop = EventLoop(component, alt=False)

    def _raise_each_time() -> None:
        raise exc_factory()

    event_loop._loop = Mock(side_effect=_raise_each_time)
    event_loop.start = Mock()
    event_loop.stop = Mock()

    event_loop.run()
    assert event_loop.stop.call_count == expected_stop_calls


@patch("pigit.termui.event_loop.logging.getLogger")
@patch("pigit.termui.event_loop.Session")
def test_run_unexpected_exception_logs_with_exception(mock_session_cls, mock_get_logger):
    session_cm = MagicMock()
    session_inner = MagicMock()
    session_inner.renderer = MagicMock()
    session_cm.__enter__.return_value = session_inner
    session_cm.__exit__.return_value = None
    mock_session_cls.return_value = session_cm

    mock_log = MagicMock()
    mock_get_logger.return_value = mock_log

    component = ComponentMock()
    event_loop = EventLoop(component, alt=False)
    event_loop._loop = Mock(side_effect=RuntimeError("boom"))
    event_loop.start = Mock()
    event_loop.stop = Mock()

    event_loop.run()

    event_loop.stop.assert_called_once()
    mock_log.exception.assert_called_once()


@pytest.mark.parametrize(
    "size, expected_resize_calls",
    [
        ((80, 24), 1),
        ((100, 40), 1),
    ],
)
def test_resize(size, expected_resize_calls):
    component = ComponentMock()
    event_loop = EventLoop(component, alt=False)
    event_loop.get_term_size = Mock(return_value=size)
    event_loop._child.resize = Mock()

    event_loop.resize()

    event_loop._child.resize.assert_called_once_with(size)


@pytest.mark.parametrize(
    "timeout, expected_set_timeout_calls",
    [
        (0.1, 1),
        (1.0, 1),
        (5.0, 1),
    ],
)
def test_set_input_timeouts(timeout, expected_set_timeout_calls):
    component = ComponentMock()
    event_loop = EventLoop(component, alt=False)
    event_loop._input_handle.set_input_timeouts = Mock()

    event_loop.set_input_timeouts(timeout)

    event_loop._input_handle.set_input_timeouts.assert_called_once_with(timeout)


class _Leaf(Component):
    NAME = "leaf"

    def _render_surface(self, surface):
        pass

    def fresh(self):
        pass


@pytest.mark.parametrize(
    "batch, expected_outcome",
    [
        ([["z"]], "binding"),
        ([["window resize"]], "resize"),
        ([["unbound"]], "child"),
    ],
)
def test_loop_string_dispatch_calls_hooks_with_outcome(batch, expected_outcome):
    """``before_dispatch_key`` / ``after_dispatch_key`` run only on string-key dispatch."""

    class _Hooked(AppEventLoop):
        BINDINGS = [("z", "on_z")]

        def __init__(self) -> None:
            super().__init__(_Leaf(), alt=False)
            self.trace: list = []

        def on_z(self) -> None:
            self.trace.append("handler")

        def before_dispatch_key(self, key: str) -> None:
            self.trace.append(("before", key))

        def after_dispatch_key(self, key: str, outcome: str) -> None:
            self.trace.append(("after", key, outcome))

    loop = _Hooked()
    loop._renderer = MagicMock()
    loop.get_term_size = Mock(return_value=(80, 24))
    loop._child._handle_event = Mock()

    key = batch[0][0]
    loop._input_handle = Mock()
    loop._input_handle.get_input.side_effect = [batch, KeyboardInterrupt()]

    loop._run_impl()

    assert ("before", key) in loop.trace
    assert ("after", key, expected_outcome) in loop.trace
    if expected_outcome == "child":
        loop._child._handle_event.assert_called_once_with("unbound")


def test_loop_real_time_idle_does_not_call_dispatch_hooks():
    class _Hooked(AppEventLoop):
        def __init__(self) -> None:
            super().__init__(_Leaf(), real_time=True, alt=False)

    loop = _Hooked()
    loop._renderer = MagicMock()
    loop.get_term_size = Mock(return_value=(80, 24))
    loop.before_dispatch_key = Mock()
    loop.after_dispatch_key = Mock()
    loop._input_handle = Mock()
    loop._input_handle.get_input.side_effect = [[], KeyboardInterrupt()]

    loop._run_impl()

    loop.before_dispatch_key.assert_not_called()
    loop.after_dispatch_key.assert_not_called()


def test_loop_overlay_open_routes_to_child_handle_event():
    """When the root reports an open overlay, keys route to child._handle_event."""

    class _OverlayRoot(ComponentMock):
        def has_overlay_open(self):
            return True

    class _Hooked(AppEventLoop):
        def __init__(self) -> None:
            super().__init__(_OverlayRoot(), alt=False)
            self.trace: list = []

        def after_dispatch_key(self, key: str, outcome: str) -> None:
            self.trace.append((key, outcome))

    loop = _Hooked()
    loop._renderer = MagicMock()
    loop.get_term_size = Mock(return_value=(80, 24))
    loop._child._handle_event = Mock()

    loop._input_handle = Mock()
    loop._input_handle.get_input.side_effect = [[["k"]], KeyboardInterrupt()]

    loop._run_impl()

    loop._child._handle_event.assert_called_once_with("k")
    assert ("k", "overlay") in loop.trace


def test_loop_overlay_open_maps_to_overlay_outcome():
    """When overlay is open, outcome is ``overlay`` regardless of inner result."""

    class _OverlayRoot(ComponentMock):
        def has_overlay_open(self):
            return True

    class _Hooked(AppEventLoop):
        def __init__(self) -> None:
            super().__init__(_OverlayRoot(), alt=False)
            self.trace: list = []

        def after_dispatch_key(self, key: str, outcome: str) -> None:
            self.trace.append((key, outcome))

    loop = _Hooked()
    loop._renderer = MagicMock()
    loop.get_term_size = Mock(return_value=(80, 24))
    loop._child._handle_event = Mock()

    loop._input_handle = Mock()
    loop._input_handle.get_input.side_effect = [[["k"]], KeyboardInterrupt()]

    loop._run_impl()

    loop._child._handle_event.assert_called_once_with("k")
    assert ("k", "overlay") in loop.trace


def test_resize_calls_renderer_clear_cache():
    component = ComponentMock()
    event_loop = EventLoop(component, alt=False)
    event_loop.get_term_size = Mock(return_value=(80, 24))
    event_loop._renderer = MagicMock()

    event_loop.resize()

    event_loop._renderer.clear_cache.assert_called_once()


def test_render_surface_path():
    from pigit.termui.surface import Surface

    component = ComponentMock()
    event_loop = EventLoop(component, alt=False)
    event_loop._size = (10, 5)
    event_loop._renderer = MagicMock()
    component._render_surface = Mock()

    event_loop.render()

    component._render_surface.assert_called_once()
    surface = component._render_surface.call_args[0][0]
    assert isinstance(surface, Surface)
    assert surface.width == 10
    assert surface.height == 5


def test_dispatch_semantic_string_binding_renders():
    class _Quick(AppEventLoop):
        BINDINGS = [("r", "on_r")]

        def on_r(self) -> None:
            pass

    loop = _Quick(_Leaf(), alt=False)
    loop._renderer = MagicMock()
    loop.get_term_size = Mock(return_value=(80, 24))
    loop.render = Mock()

    outcome = loop._dispatch_semantic_string("r")

    assert outcome == "binding"
    loop.render.assert_called_once()


def test_app_event_loop_accepts_callable_binding():
    def quit_cb() -> None:
        raise ExitEventLoop("bye")

    class _Quick(AppEventLoop):
        BINDINGS = [("q", quit_cb)]

    loop = _Quick(_Leaf(), alt=False)
    loop._renderer = MagicMock()
    loop.get_term_size = Mock(return_value=(80, 24))
    loop._input_handle = Mock()
    loop._input_handle.get_input.side_effect = [[["q"]], KeyboardInterrupt()]

    loop._run_impl()


def test_overlay_controller_returns_closed_after_error_when_dispatch_raises() -> None:
    """Fatal errors during overlay dispatch must clear the slot and return a distinct result."""

    from pigit.termui.overlay_controller import OverlayController
    from pigit.termui.overlay_kinds import OverlayDispatchResult, OverlayKind

    class _BrokenSurface:
        open = True

        def dispatch_overlay_key(self, key: str) -> OverlayDispatchResult:
            raise RuntimeError("simulated overlay handler failure")

        def hide(self) -> None:
            pass

        def _render_surface(self, surface) -> None:
            pass

    host = MagicMock()
    host.overlay_kind = OverlayKind.POPUP
    host._active_popup = _BrokenSurface()
    host.force_close_overlay_after_error = Mock()

    ctrl = OverlayController()
    assert ctrl.dispatch(host, "x") is OverlayDispatchResult.CLOSED_AFTER_ERROR
    host.force_close_overlay_after_error.assert_called_once()


def test_overlay_controller_question_mark_toggles_help_when_help_open() -> None:
    """``?`` must close help while help is open (App-level binding is not run in overlay mode)."""

    from pigit.termui.overlay_controller import OverlayController
    from pigit.termui.components_overlay import HelpPanel, Popup
    from pigit.termui.overlay_kinds import OverlayDispatchResult, OverlayKind

    root = MagicMock()
    root.overlay_kind = OverlayKind.POPUP
    help_panel = HelpPanel()
    popup = Popup(help_panel, session_owner=root)
    root._active_popup = popup

    ctrl = OverlayController()
    assert ctrl.dispatch(root, "?") is OverlayDispatchResult.HANDLED_IMPLICIT
    root.end_popup_session.assert_called_once()


def test_bind_renderer_tree_recurses_into_children():
    from pigit.termui.components import TabView

    class _Leaf(Component):
        NAME = "leaf"

        def _render_surface(self, surface):
            pass

        def fresh(self):
            pass

    a, b = _Leaf(), _Leaf()
    root = TabView({"main": a, "b": b})

    loop = AppEventLoop(root, alt=False)
    renderer = MagicMock()
    loop._bind_renderer_tree(root, renderer)

    assert root._renderer is renderer
    assert a._renderer is renderer
    assert b._renderer is renderer


def test_clear_screen_when_renderer_none_does_not_crash():
    loop = AppEventLoop(ComponentMock(), alt=False)
    loop._renderer = None
    loop.clear_screen()


def test_context_manager_start_stop():
    loop = AppEventLoop(ComponentMock(), alt=False)
    loop.start = Mock()
    loop.stop = Mock()
    with loop:
        pass
    loop.start.assert_called_once()
    loop.stop.assert_called_once()


def test_loop_mouse_event_is_ignored():
    class _Hooked(AppEventLoop):
        def __init__(self) -> None:
            super().__init__(_Leaf(), alt=False)

    loop = _Hooked()
    loop._renderer = MagicMock()
    loop.get_term_size = Mock(return_value=(80, 24))
    loop.before_dispatch_key = Mock()
    loop.after_dispatch_key = Mock()
    loop._input_handle = Mock()
    loop._input_handle.get_input.side_effect = [[[("mouse down", 1, 2, 3)]], KeyboardInterrupt()]

    loop._run_impl()

    loop.before_dispatch_key.assert_not_called()
    loop.after_dispatch_key.assert_not_called()


def test_quit_raises_exit_event_loop():
    loop = AppEventLoop(ComponentMock(), alt=False)
    with pytest.raises(ExitEventLoop, match="bye"):
        loop.quit("bye", exit_code=42, result_message="msg")
