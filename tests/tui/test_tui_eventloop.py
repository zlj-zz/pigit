import pytest
from unittest.mock import MagicMock, Mock, patch

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
    """Alternate screen is applied inside ``Session`` in ``run()``, not in ``start()``."""

    component = ComponentMock()
    event_loop = EventLoop(component, real_time=real_time, alt=alt)
    with patch.object(EventLoop, "to_alt_screen") as mock_to_alt_screen, patch.object(
        EventLoop, "to_normal_screen"
    ) as mock_to_normal_screen:

        event_loop.start()
        event_loop.stop()

        mock_to_alt_screen.assert_not_called()
        mock_to_normal_screen.assert_not_called()


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
    "exception, expected_stop_calls",
    [
        (ExitEventLoop, 1),
        (KeyboardInterrupt, 1),
        (EOFError, 1),
        (Exception, 1),
    ],
)
@patch("pigit.termui.event_loop.Session")
def test_run_exception_handling(mock_session_cls, exception, expected_stop_calls):
    session_cm = MagicMock()
    session_inner = MagicMock()
    session_inner.renderer = MagicMock()
    session_cm.__enter__.return_value = session_inner
    session_cm.__exit__.return_value = None
    mock_session_cls.return_value = session_cm

    component = ComponentMock()
    event_loop = EventLoop(component, alt=False)
    event_loop._loop = Mock(side_effect=exception())
    event_loop.start = Mock()
    event_loop.stop = Mock()

    with pytest.raises(exception):
        event_loop._loop()

    event_loop.run()
    assert event_loop.stop.call_count == expected_stop_calls


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
