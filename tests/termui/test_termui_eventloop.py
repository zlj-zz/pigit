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

from pigit.termui.component import Component
from pigit.termui.input import TermuiInputBridge
from pigit.termui.event_loop import AppEventLoop, ExitEventLoop
from pigit.termui.input import InputTerminal
from pigit.termui._runtime_context import (
    RuntimeContext,
    _runtime_ctx,
    set_renderer,
    reset_renderer,
)

EventLoop = AppEventLoop


@pytest.fixture(autouse=True)
def _runtime_context():
    """Provide a fresh RuntimeContext for event loop tests."""
    runtime = RuntimeContext()
    token = _runtime_ctx.set(runtime)
    yield
    _runtime_ctx.reset(token)


@pytest.fixture
def mock_renderer():
    """Provide a mock renderer in context for unit tests."""
    renderer = MagicMock()
    set_renderer(renderer)
    try:
        yield renderer
    finally:
        reset_renderer()


from pigit.termui.types import OverlayDispatchResult


class ComponentMock(Component):
    def __init__(self):
        super().__init__()

    def resize(self, size):
        pass

    def paint(self, surface):
        pass

    def _handle_event(self, event):
        pass

    def has_overlay_open(self):
        return False

    def try_dispatch_overlay(self, key):
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
        (lambda: RuntimeError("x"), 1, True),
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


@patch("pigit.termui.event_loop._logger")
@patch("pigit.termui.event_loop.Session")
def test_run_unexpected_exception_logs_with_exception(mock_session_cls, mock_logger):
    session_cm = MagicMock()
    session_inner = MagicMock()
    session_inner.renderer = MagicMock()
    session_cm.__enter__.return_value = session_inner
    session_cm.__exit__.return_value = None
    mock_session_cls.return_value = session_cm

    component = ComponentMock()
    event_loop = EventLoop(component, alt=False)
    event_loop._loop = Mock(side_effect=RuntimeError("boom"))
    event_loop.start = Mock()
    event_loop.stop = Mock()

    with pytest.raises(RuntimeError, match="boom"):
        event_loop.run()

    event_loop.stop.assert_called_once()
    mock_logger.exception.assert_called_once()


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


class _Leaf(Component):
    NAME = "leaf"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def has_overlay_open(self):
        return False

    def paint(self, surface):
        pass

    def refresh(self):
        pass


@pytest.mark.parametrize(
    "batch, expected_outcome",
    [
        ([["z"]], "binding"),
        ([["window resize"]], "resize"),
        ([["unbound"]], "child"),
    ],
)
def test_loop_string_dispatch_calls_hooks_with_outcome(
    mock_renderer, batch, expected_outcome
):
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
    loop._input_handle.get_key.side_effect = [key, ExitEventLoop("stop")]

    with pytest.raises(ExitEventLoop):
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
    loop._input_handle.get_key.side_effect = [None, ExitEventLoop("stop")]

    with pytest.raises(ExitEventLoop):
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
    loop._input_handle.get_key.side_effect = ["k", ExitEventLoop("stop")]

    with pytest.raises(ExitEventLoop):
        loop._run_impl()

    loop._child._handle_event.assert_called_once_with("k")
    assert ("k", "child") in loop.trace


def test_resize_calls_renderer_clear_cache():
    from pigit.termui._runtime_context import set_renderer, reset_renderer

    component = ComponentMock()
    event_loop = EventLoop(component, alt=False)
    event_loop.get_term_size = Mock(return_value=(80, 24))
    mock_renderer = MagicMock()
    set_renderer(mock_renderer)
    try:
        event_loop.resize()
        mock_renderer.clear_cache.assert_called_once()
    finally:
        reset_renderer()


def testpaint_path(mock_renderer):
    from pigit.termui.surface import Surface

    component = ComponentMock()
    event_loop = EventLoop(component, alt=False)
    event_loop._size = (10, 5)
    # renderer from mock_renderer fixture
    component.paint = Mock()

    event_loop.render()

    component.paint.assert_called_once()
    surface = component.paint.call_args[0][0]
    assert isinstance(surface, Surface)
    assert surface.width == 10
    assert surface.height == 5


def test_dispatch_semantic_string_binding_requests_render(mock_renderer):
    class _Quick(AppEventLoop):
        BINDINGS = [("r", "on_r")]

        def on_r(self) -> None:
            pass

    loop = _Quick(_Leaf(), alt=False)
    # renderer from mock_renderer fixture
    loop.get_term_size = Mock(return_value=(80, 24))

    outcome = loop._dispatch_semantic_string("r")

    assert outcome == "binding"
    assert loop._render_requested is True


def test_app_event_loop_accepts_callable_binding(mock_renderer):
    def quit_cb() -> None:
        raise ExitEventLoop("bye")

    class _Quick(AppEventLoop):
        BINDINGS = [("q", quit_cb)]

    loop = _Quick(_Leaf(), alt=False)
    # renderer from mock_renderer fixture
    loop.get_term_size = Mock(return_value=(80, 24))
    loop._input_handle = Mock()
    loop._input_handle.get_key.side_effect = ["q", ExitEventLoop("stop")]

    with pytest.raises(ExitEventLoop, match="bye"):
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
    """``?`` toggles help popup via HelpPanel.toggle (explicit HANDLED_EXPLICIT)."""
    from pigit.termui._layer import LayerStack
    from pigit.termui.widgets import HelpPanel, Popup
    from pigit.termui.types import LayerKind, OverlayDispatchResult
    from pigit.termui._runtime_context import set_overlay_host

    # Create LayerStack and real host mock that uses it
    stack = LayerStack()
    root = MagicMock()
    root._layer_stack = stack

    set_overlay_host(root)
    try:
        help_panel = HelpPanel()
        popup = Popup(help_panel)
        # Popup auto-binds toggle; no manual wiring needed.
        popup.open = True

        # Push popup to MODAL layer
        stack.push(LayerKind.MODAL, popup)

        # Dispatch "?" key
        result = stack.dispatch("?")

        assert result is OverlayDispatchResult.HANDLED_EXPLICIT
        assert not stack.has_any_open()
    finally:
        from pigit.termui._runtime_context import reset_overlay_host

        reset_overlay_host()


def test_renderer_accessed_via_context():
    """Renderer is now accessed via ContextVar instead of explicit binding."""
    from pigit.termui.containers import TabView
    from pigit.termui._runtime_context import (
        set_renderer,
        reset_renderer,
        get_renderer,
    )

    class _Leaf(Component):
        NAME = "leaf"

        def paint(self, surface):
            pass

        def refresh(self):
            pass

    a, b = _Leaf(), _Leaf()
    root = TabView(children=[a, b])

    # Set renderer via ContextVar
    renderer = MagicMock()
    set_renderer(renderer)
    try:
        # All components can now access renderer via context
        assert root.renderer is renderer
        assert a.renderer is renderer
        assert b.renderer is renderer
        assert get_renderer() is renderer
    finally:
        reset_renderer()


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


def test_loop_mouse_event_is_handled(mock_renderer):
    from pigit.termui.mouse import MouseButton, MouseEvent, MouseKind

    class _Hooked(AppEventLoop):
        def __init__(self) -> None:
            super().__init__(_Leaf(), alt=False)

    loop = _Hooked()
    # renderer from mock_renderer fixture
    loop.get_term_size = Mock(return_value=(80, 24))
    loop.before_dispatch_key = Mock()
    loop.after_dispatch_key = Mock()
    loop.before_mouse_event = Mock()
    loop._input_handle = Mock()
    loop._input_handle.get_key.side_effect = [
        MouseEvent(col=1, row=1, button=MouseButton.LEFT, kind=MouseKind.PRESS),
        ExitEventLoop("stop"),
    ]

    with pytest.raises(ExitEventLoop):
        loop._run_impl()

    loop.before_mouse_event.assert_called_once()
    loop.before_dispatch_key.assert_not_called()
    loop.after_dispatch_key.assert_not_called()


def test_loop_mouse_event_requests_render(mock_renderer):
    from pigit.termui.mouse import MouseButton, MouseEvent, MouseKind

    class _Hooked(AppEventLoop):
        def __init__(self) -> None:
            super().__init__(_Leaf(), alt=False)

    loop = _Hooked()
    loop.get_term_size = Mock(return_value=(80, 24))
    loop.render = Mock()
    loop._input_handle = Mock()
    # None drains the batch (render fires), then the sentinel stops the loop.
    loop._input_handle.get_key.side_effect = [
        MouseEvent(col=1, row=1, button=MouseButton.LEFT, kind=MouseKind.PRESS),
        None,
        ExitEventLoop("stop"),
    ]

    with pytest.raises(ExitEventLoop):
        loop._run_impl()

    # Initial render (start -> resize) plus one batched render for the batch.
    assert loop.render.call_count == 2


def test_quit_raises_exit_event_loop():
    loop = AppEventLoop(ComponentMock(), alt=False)
    with pytest.raises(ExitEventLoop, match="bye"):
        loop.quit("bye", exit_code=42, result_message="msg")


# ---- Timer tests ----


def test_add_interval_fires_callback(mock_renderer):
    """Timer callback fires after interval elapses."""
    loop = AppEventLoop(_Leaf(), alt=False)
    loop.get_term_size = Mock(return_value=(80, 24))
    loop._input_handle = Mock()
    loop._input_handle.get_key.side_effect = [
        None,  # first poll: no keys, timer fires
        ExitEventLoop("stop"),
    ]

    calls = []
    loop.add_interval(0.0001, lambda: calls.append("fired"))

    with pytest.raises(ExitEventLoop):
        loop._run_impl()

    assert "fired" in calls


def test_remove_interval_stops_firing(mock_renderer):
    """remove_interval prevents further timer firings."""
    loop = AppEventLoop(_Leaf(), alt=False)
    loop.get_term_size = Mock(return_value=(80, 24))
    loop._input_handle = Mock()
    loop._input_handle.get_key.side_effect = [
        None,  # first poll
        None,  # second poll
        ExitEventLoop("stop"),
    ]

    calls = []
    tid = loop.add_interval(0.0001, lambda: calls.append("fired"))
    loop.remove_interval(tid)

    with pytest.raises(ExitEventLoop):
        loop._run_impl()

    assert calls == []


def test_timer_exception_isolated(mock_renderer):
    """Timer callback exception does not break the loop or other timers."""
    loop = AppEventLoop(_Leaf(), alt=False)
    loop.get_term_size = Mock(return_value=(80, 24))
    loop._input_handle = Mock()
    loop._input_handle.get_key.side_effect = [
        None,  # both timers fire
        ExitEventLoop("stop"),
    ]

    good_calls = []
    loop.add_interval(0.0001, lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    loop.add_interval(0.0001, lambda: good_calls.append("ok"))

    with pytest.raises(ExitEventLoop):
        loop._run_impl()

    assert "ok" in good_calls


def test_multiple_timers_fire_independently(mock_renderer):
    """Multiple timers with different intervals fire independently."""
    loop = AppEventLoop(_Leaf(), alt=False)
    loop.get_term_size = Mock(return_value=(80, 24))
    loop._input_handle = Mock()
    loop._input_handle.get_key.side_effect = [
        None,
        ExitEventLoop("stop"),
    ]

    fast_calls = []
    slow_calls = []
    loop.add_interval(0.0001, lambda: fast_calls.append("fast"))
    loop.add_interval(3600.0, lambda: slow_calls.append("slow"))

    with pytest.raises(ExitEventLoop):
        loop._run_impl()

    assert len(fast_calls) >= 1
    assert slow_calls == []


def test_stop_clears_timers(mock_renderer):
    """stop() clears all registered timers."""
    loop = AppEventLoop(_Leaf(), alt=False)
    loop.add_interval(1.0, lambda: None)
    assert len(loop._timers) == 1
    loop.stop()
    assert len(loop._timers) == 0


# ---- Batched input rendering (mouse-wheel ghost-scroll fix) ----


def _wheel(row: int = 1) -> "object":
    from pigit.termui.mouse import MouseButton, MouseEvent, MouseKind

    return MouseEvent(
        col=1, row=row, button=MouseButton.WHEEL_DOWN, kind=MouseKind.PRESS
    )


def _render_counting_loop(renderer, **kwargs):
    """A _Leaf loop with a mocked render and mocked input handle."""
    from pigit.termui.event_loop import AppEventLoop

    class _Hooked(AppEventLoop):
        def __init__(self) -> None:
            super().__init__(_Leaf(), alt=False)

    loop = _Hooked()
    loop.get_term_size = Mock(return_value=(80, 24))
    loop.render = Mock()
    loop._input_handle = Mock()
    for k, v in kwargs.items():
        setattr(loop, k, v)
    return loop


def test_wheel_burst_renders_once(mock_renderer):
    """A backlog of wheel events drains in one batch with a single render."""
    loop = _render_counting_loop(mock_renderer)
    loop._input_handle.get_key.side_effect = (
        [_wheel()] * 8 + [None, ExitEventLoop("stop")]
    )

    with pytest.raises(ExitEventLoop):
        loop._run_impl()

    # Initial resize render + exactly one batched render for all 8 wheels.
    assert loop.render.call_count == 2


def test_wheel_burst_drains_every_event(mock_renderer):
    """Batching merges renders, never drops events."""
    loop = _render_counting_loop(mock_renderer)
    loop._child._handle_mouse = Mock()
    loop._input_handle.get_key.side_effect = (
        [_wheel()] * 8 + [None, ExitEventLoop("stop")]
    )

    with pytest.raises(ExitEventLoop):
        loop._run_impl()

    assert loop._child._handle_mouse.call_count == 8  # every wheel reached the child


def test_wheel_batch_idle_does_not_render_again(mock_renderer):
    """停滚即停: once the backlog drains, idle polls add no render."""
    loop = _render_counting_loop(mock_renderer)
    loop._input_handle.get_key.side_effect = [
        _wheel(),
        None,  # batch 1 drains → one render
        None,  # idle poll — nothing to render
        ExitEventLoop("stop"),
    ]

    with pytest.raises(ExitEventLoop):
        loop._run_impl()

    # Initial resize render + the single batch render; idle poll adds none.
    assert loop.render.call_count == 2


def test_exit_event_loop_mid_batch_stops_draining(mock_renderer):
    """S1: quit raised while draining propagates and drops the rest of the batch."""

    class _Quitting(_Leaf):
        def __init__(self) -> None:
            super().__init__()
            self.handled = 0

        def _handle_mouse(self, event) -> None:
            self.handled += 1
            if self.handled >= 2:
                raise ExitEventLoop("stop")

    class _Hooked(AppEventLoop):
        def __init__(self) -> None:
            super().__init__(_Quitting(), alt=False)

    loop = _Hooked()
    loop.get_term_size = Mock(return_value=(80, 24))
    loop.render = Mock()
    loop._input_handle = Mock()
    # No None between wheels: quit must interrupt the drain itself.
    loop._input_handle.get_key.side_effect = [_wheel()] * 5

    with pytest.raises(ExitEventLoop, match="stop"):
        loop._run_impl()

    assert loop._child.handled == 2  # remaining 3 wheels are dropped


def test_single_key_press_renders_once(mock_renderer):
    """Regression: one key press still renders exactly once (no per-event lag)."""

    class _Hooked(AppEventLoop):
        BINDINGS = [("z", "on_z")]

        def __init__(self) -> None:
            super().__init__(_Leaf(), alt=False)
            self.pressed = 0

        def on_z(self) -> None:
            self.pressed += 1

    loop = _Hooked()
    loop.get_term_size = Mock(return_value=(80, 24))
    loop.render = Mock()
    loop._input_handle = Mock()
    loop._input_handle.get_key.side_effect = ["z", None, ExitEventLoop("stop")]

    with pytest.raises(ExitEventLoop):
        loop._run_impl()

    assert loop.pressed == 1
    # Initial resize render + one batched render for the single key.
    assert loop.render.call_count == 2
