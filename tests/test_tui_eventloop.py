import pytest
from unittest.mock import Mock, patch
from pigit.tui.event_loop import EventLoop, ExitEventLoop
from pigit.tui.input import InputTerminal, PosixInput


class ComponentMock:
    def resize(self, size):
        pass

    def _render(self):
        pass

    def _handle_event(self, event):
        pass


@pytest.mark.parametrize("real_time, alt, expected_start_calls", [
    (True, True, "to_alt_screen"),  # ID: real_time-true_alt-true
    (False, False, "to_normal_screen"),  # ID: real_time-false_alt-false
    (True, False, None),  # ID: real_time-true_alt-false
    (False, True, "to_alt_screen"),  # ID: real_time-false_alt-true
])
def test_start_stop(real_time, alt, expected_start_calls):
    # Arrange
    component = ComponentMock()
    event_loop = EventLoop(component, real_time=real_time, alt=alt)
    with patch.object(EventLoop, 'to_alt_screen') as mock_to_alt_screen, \
         patch.object(EventLoop, 'to_normal_screen') as mock_to_normal_screen:

        # Act
        event_loop.start()
        event_loop.stop()

        # Assert
        if expected_start_calls == "to_alt_screen":
            mock_to_alt_screen.assert_called_once()
            mock_to_normal_screen.assert_called_once()
        else:
            mock_to_alt_screen.assert_not_called()
            mock_to_normal_screen.assert_not_called()


@pytest.mark.parametrize(
    "input_handle, expected_instance",
    [
        (None, PosixInput),  # ID: input_handle-none
        (Mock(spec=InputTerminal), InputTerminal),  # ID: input_handle-mock
    ],
)
def test_init_input_handle(input_handle, expected_instance):
    # Arrange
    component = ComponentMock()

    # Act
    event_loop = EventLoop(component, input_handle=input_handle, alt=False)

    # Assert
    assert isinstance(event_loop._input_handle, expected_instance)


@pytest.mark.parametrize(
    "exception, expected_stop_calls",
    [
        (ExitEventLoop, 1),  # ID: exception-ExitEventLoop
        (KeyboardInterrupt, 1),  # ID: exception-KeyboardInterrupt
        (EOFError, 1),  # ID: exception-EOFError
        (Exception, 1),  # ID: exception-Other
    ],
)
def test_run_exception_handling(exception, expected_stop_calls):
    # Arrange
    print("eeeexcepiton:", exception)
    component = ComponentMock()
    event_loop = EventLoop(component, alt=False)
    event_loop._loop = Mock(side_effect=exception())
    event_loop.start = Mock()
    event_loop.stop = Mock()

    # Act
    with pytest.raises(exception):
        event_loop._loop()

    # Assert
    event_loop.run()
    assert event_loop.stop.call_count == expected_stop_calls


@pytest.mark.parametrize(
    "size, expected_resize_calls",
    [
        ((80, 24), 1),  # ID: size-80x24
        ((100, 40), 1),  # ID: size-100x40
    ],
)
def test_resize(size, expected_resize_calls):
    # Arrange
    component = ComponentMock()
    event_loop = EventLoop(component, alt=False)
    event_loop.get_term_size = Mock(return_value=size)
    event_loop._child.resize = Mock()

    # Act
    event_loop.resize()

    # Assert
    event_loop._child.resize.assert_called_once_with(size)


@pytest.mark.parametrize(
    "timeout, expected_set_timeout_calls",
    [
        (0.1, 1),  # ID: timeout-0.1
        (1.0, 1),  # ID: timeout-1.0
        (5.0, 1),  # ID: timeout-5.0
    ],
)
def test_set_input_timeouts(timeout, expected_set_timeout_calls):
    # Arrange
    component = ComponentMock()
    event_loop = EventLoop(component, alt=False)
    event_loop._input_handle.set_input_timeouts = Mock()

    # Act
    event_loop.set_input_timeouts(timeout)

    # Assert
    event_loop._input_handle.set_input_timeouts.assert_called_once_with(timeout)
