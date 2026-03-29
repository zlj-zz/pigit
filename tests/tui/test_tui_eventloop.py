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

    def _render(self):
        pass

    def _handle_event(self, event):
        pass


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

    def _render(self, size=None):
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
