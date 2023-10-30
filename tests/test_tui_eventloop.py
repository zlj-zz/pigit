import pytest
from unittest.mock import Mock, patch
from pigit.tui.event_loop import EventLoop, ExitEventLoop


@pytest.mark.parametrize(
    "alt,expected",
    [(True, 1), (False, 0)],
    ids=["alt-true", "alt-false"],
)
def test_start(alt, expected):
    # Arrange
    mock_child = Mock()
    event_loop = EventLoop(mock_child, alt=alt)
    event_loop.to_alt_screen = Mock()
    event_loop.resize = Mock()

    # Act
    event_loop.start()

    # Assert
    assert event_loop.to_alt_screen.call_count == expected
    assert event_loop.resize.call_count == 1


@pytest.mark.parametrize(
    "alt,expected",
    [(True, 1), (False, 0)],
    ids=["alt-true", "alt-false"],
)
def test_stop(alt, expected):
    # Arrange
    mock_child = Mock()
    event_loop = EventLoop(mock_child, alt=alt)
    event_loop.to_normal_screen = Mock()

    # Act
    event_loop.stop()

    # Assert
    assert event_loop.to_normal_screen.call_count == expected


def test_resize():
    # Arrange
    mock_child = Mock()
    event_loop = EventLoop(mock_child)
    event_loop.clear_screen = Mock()
    event_loop._child._render = Mock()

    # Act
    event_loop.resize()

    # Assert
    mock_child.resize.assert_called_once()
    event_loop.clear_screen.assert_called_once()
    event_loop._child._render.assert_called_once()


@pytest.mark.parametrize(
    "input_key,expected",
    [([["window resize", ""]], 1), ([["other", ""]], 0)],
    ids=["resize-event", "other-event"],
)
def test_loop(input_key, expected):
    # Arrange
    mock_child = Mock()
    event_loop = EventLoop(mock_child)
    event_loop._input_handle.get_input = Mock(return_value=input_key)
    event_loop.resize = Mock()

    # Act
    event_loop._loop()

    # Assert
    assert event_loop.resize.call_count == expected


def test_run():
    # Arrange
    mock_child = Mock()
    event_loop = EventLoop(mock_child)
    event_loop._input_handle.start = Mock()
    event_loop._input_handle.stop = Mock()
    event_loop.start = Mock()
    event_loop.stop = Mock()
    event_loop._loop = Mock(side_effect=[None, KeyboardInterrupt])

    # Act
    event_loop.run()

    # Assert
    event_loop._input_handle.start.assert_called_once()
    event_loop._input_handle.stop.assert_called_once()
    event_loop.start.assert_called_once()
    event_loop.stop.assert_called_once()


def test_quit():
    # Arrange
    mock_child = Mock()
    event_loop = EventLoop(mock_child)

    # Act & Assert
    with pytest.raises(ExitEventLoop):
        event_loop.quit()
