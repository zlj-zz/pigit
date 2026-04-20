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

from pigit.termui._component_base import Component
from pigit.termui.input_bridge import TermuiInputBridge
from pigit.termui.event_loop import AppEventLoop, ExitEventLoop
from pigit.termui.input_terminal import InputTerminal
from pigit.termui._renderer_context import set_renderer, reset_renderer

EventLoop = AppEventLoop


@pytest.fixture
def mock_renderer():
    """Provide a mock renderer in context for unit tests."""
    renderer = MagicMock()
    token = set_renderer(renderer)
    try:
        yield renderer
    finally:
        reset_renderer(token)


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
        from pigit.termui.types import OverlayDispatchResult

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
    "exc_factory, expected_stop_calls, should_reraise",
    [
        (lambda: ExitEventLoop("x"), 1, True),
        (lambda: KeyboardInterrupt(), 1, True),
        (lambda: EOFError(), 1, True),
        (lambda: RuntimeError("x"), 1, False),
    ],
)
@patch("pigit.termui.event_loop.Session")
def test_run_exception_handling(
    mock_session_cls, exc_factory, expected_stop_calls, should_reraise
):
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

    if should_reraise:
        with pytest.raises(type(exc_factory())):
            event_loop.run()
    else:
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
def test_loop_string_dispatch_calls_hooks_with_outcome(mock_renderer, batch, expected_outcome):
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
    # renderer from mock_renderer fixture
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


def test_loop_real_time_idle_does_not_call_dispatch_hooks(mock_renderer):
    class _Hooked(AppEventLoop):
        def __init__(self) -> None:
            super().__init__(_Leaf(), real_time=True, alt=False)

    loop = _Hooked()
    # renderer from mock_renderer fixture
    loop.get_term_size = Mock(return_value=(80, 24))
    loop.before_dispatch_key = Mock()
    loop.after_dispatch_key = Mock()
    loop._input_handle = Mock()
    loop._input_handle.get_input.side_effect = [[], KeyboardInterrupt()]

    loop._run_impl()

    loop.before_dispatch_key.assert_not_called()
    loop.after_dispatch_key.assert_not_called()


def test_loop_overlay_open_routes_to_child_handle_event(mock_renderer):
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
    # renderer from mock_renderer fixture
    loop.get_term_size = Mock(return_value=(80, 24))
    loop._child._handle_event = Mock()

    loop._input_handle = Mock()
    loop._input_handle.get_input.side_effect = [[["k"]], KeyboardInterrupt()]

    loop._run_impl()

    loop._child._handle_event.assert_called_once_with("k")
    assert ("k", "overlay") in loop.trace


def test_loop_overlay_open_maps_to_overlay_outcome(mock_renderer):
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
    # renderer from mock_renderer fixture
    loop.get_term_size = Mock(return_value=(80, 24))
    loop._child._handle_event = Mock()

    loop._input_handle = Mock()
    loop._input_handle.get_input.side_effect = [[["k"]], KeyboardInterrupt()]

    loop._run_impl()

    loop._child._handle_event.assert_called_once_with("k")
    assert ("k", "overlay") in loop.trace


def test_resize_calls_renderer_clear_cache():
    from pigit.termui._renderer_context import set_renderer, reset_renderer
    component = ComponentMock()
    event_loop = EventLoop(component, alt=False)
    event_loop.get_term_size = Mock(return_value=(80, 24))
    mock_renderer = MagicMock()
    token = set_renderer(mock_renderer)
    try:
        event_loop.resize()
        mock_renderer.clear_cache.assert_called_once()
    finally:
        reset_renderer(token)


def test_render_surface_path(mock_renderer):
    from pigit.termui._surface import Surface

    component = ComponentMock()
    event_loop = EventLoop(component, alt=False)
    event_loop._size = (10, 5)
    # renderer from mock_renderer fixture
    component._render_surface = Mock()

    event_loop.render()

    component._render_surface.assert_called_once()
    surface = component._render_surface.call_args[0][0]
    assert isinstance(surface, Surface)
    assert surface.width == 10
    assert surface.height == 5


def test_dispatch_semantic_string_binding_renders(mock_renderer):
    class _Quick(AppEventLoop):
        BINDINGS = [("r", "on_r")]

        def on_r(self) -> None:
            pass

    loop = _Quick(_Leaf(), alt=False)
    # renderer from mock_renderer fixture
    loop.get_term_size = Mock(return_value=(80, 24))
    loop.render = Mock()

    outcome = loop._dispatch_semantic_string("r")

    assert outcome == "binding"
    loop.render.assert_called_once()


def test_app_event_loop_accepts_callable_binding(mock_renderer):
    def quit_cb() -> None:
        raise ExitEventLoop("bye")

    class _Quick(AppEventLoop):
        BINDINGS = [("q", quit_cb)]

    loop = _Quick(_Leaf(), alt=False)
    # renderer from mock_renderer fixture
    loop.get_term_size = Mock(return_value=(80, 24))
    loop._input_handle = Mock()
    loop._input_handle.get_input.side_effect = [[["q"]], KeyboardInterrupt()]

    loop._run_impl()


def test_layer_stack_error_recovery_closes_modal() -> None:
    """Fatal errors during overlay dispatch must clear the slot and return CLOSED_AFTER_ERROR."""
    from pigit.termui._layer import LayerStack
    from pigit.termui.types import LayerKind, OverlayDispatchResult

    class _BrokenSurface:
        open = True
        _hide_called = False
        _reset_called = False

        def dispatch_overlay_key(self, key: str) -> OverlayDispatchResult:
            raise RuntimeError("simulated overlay handler failure")

        def hide(self) -> None:
            self._hide_called = True

        def reset_state(self) -> None:
            self._reset_called = True

    stack = LayerStack()
    broken = _BrokenSurface()
    stack.push(LayerKind.MODAL, broken)

    result = stack.dispatch("x")

    assert result is OverlayDispatchResult.CLOSED_AFTER_ERROR
    assert stack.is_empty(LayerKind.MODAL)
    assert broken._hide_called
    assert broken._reset_called


def test_layer_stack_question_mark_toggles_help_popup() -> None:
    """``?`` toggles help popup via Popup.dispatch_overlay_key (implicit HANDLED_IMPLICIT)."""
    from pigit.termui._layer import LayerStack
    from pigit.termui._overlay_components import HelpPanel, Popup
    from pigit.termui.types import LayerKind, OverlayDispatchResult

    # Create LayerStack and mock host that uses it
    stack = LayerStack()
    root = MagicMock()
    root._layer_stack = stack

    help_panel = HelpPanel()
    popup = Popup(help_panel, session_owner=root)
    popup.open = True

    # Push popup to MODAL layer
    stack.push(LayerKind.MODAL, popup)

    # Dispatch "?" key
    result = stack.dispatch("?")

    assert result is OverlayDispatchResult.HANDLED_IMPLICIT
    root.end_popup_session.assert_called_once()


def test_renderer_accessed_via_context():
    """Renderer is now accessed via ContextVar instead of explicit binding."""
    from pigit.termui._component_containers import TabView
    from pigit.termui._renderer_context import set_renderer, reset_renderer, get_renderer

    class _Leaf(Component):
        NAME = "leaf"

        def _render_surface(self, surface):
            pass

        def fresh(self):
            pass

    a, b = _Leaf(), _Leaf()
    root = TabView({"main": a, "b": b})

    # Set renderer via ContextVar
    renderer = MagicMock()
    token = set_renderer(renderer)
    try:
        # All components can now access renderer via context
        assert root.renderer is renderer
        assert a.renderer is renderer
        assert b.renderer is renderer
        assert get_renderer() is renderer
    finally:
        reset_renderer(token)


def test_clear_screen_when_renderer_none_does_not_crash():
    loop = AppEventLoop(ComponentMock(), alt=False)
    # renderer not needed
    loop.clear_screen()


def test_context_manager_start_stop():
    loop = AppEventLoop(ComponentMock(), alt=False)
    loop.start = Mock()
    loop.stop = Mock()
    with loop:
        pass
    loop.start.assert_called_once()
    loop.stop.assert_called_once()


def test_loop_mouse_event_is_ignored(mock_renderer):
    class _Hooked(AppEventLoop):
        def __init__(self) -> None:
            super().__init__(_Leaf(), alt=False)

    loop = _Hooked()
    # renderer from mock_renderer fixture
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
