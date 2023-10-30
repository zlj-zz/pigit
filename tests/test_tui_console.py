import pytest
from unittest.mock import patch, call
from pigit.tui.console import Cursor, Signal, Term


@pytest.mark.parametrize(
    "attribute, expected_value",
    [
        ("hide_cursor", "\033[?25l"),
        ("show_cursor", "\033[?25h"),
        ("alt_screen", "\033[?1049h"),
        ("normal_screen", "\033[?1049l"),
        ("clear_screen", "\033[2J\033[0;0f"),
        ("mouse_on", "\033[?1002h\033[?1015h\033[?1006h"),
        ("mouse_off", "\033[?1002l"),
        ("mouse_direct_on", "\033[?1003h"),
        ("mouse_direct_off", "\033[?1003l"),
        ("term_space", " "),
    ],
    ids=[
        "hide_cursor_test",
        "show_cursor_test",
        "alt_screen_test",
        "normal_screen_test",
        "clear_screen_test",
        "mouse_on_test",
        "mouse_off_test",
        "mouse_direct_on_test",
        "mouse_direct_off_test",
        "term_space_test",
    ],
)
def test_signal_attributes(attribute, expected_value):
    # Arrange
    # No arrangement necessary as we are directly accessing class variables

    # Act
    actual_value = getattr(Signal, attribute)

    # Assert
    assert (
        actual_value == expected_value
    ), f"Expected {attribute} to be {expected_value}, but got {actual_value}"


@pytest.mark.parametrize(
    "method, expected_output",
    [
        ("to_alt_screen", Signal.alt_screen + Signal.hide_cursor),
        ("to_normal_screen", Signal.normal_screen + Signal.show_cursor),
        ("clear_screen", Signal.clear_screen),
    ],
    ids=["alt_screen", "normal_screen", "clear_screen"],
)
def test_term_methods(method, expected_output):
    # Arrange
    term = Term()

    with patch("pigit.tui.console._stdout") as mock_stdout:
        # Act
        getattr(term, method)()

        # Assert
        mock_stdout.assert_called_once_with(expected_output)


class TestCursor:
    # Test for Cursor.to method
    @pytest.mark.parametrize(
        "row, col, expected",
        [
            (1, 1, "\033[1;1f"),  # Test with minimum values
            (100, 100, "\033[100;100f"),  # Test with large values
            (0, 0, "\033[0;0f"),  # Test with zero values
        ],
        ids=["min-values", "large-values", "zero-values"],
    )
    def test_to(self, row, col, expected, mocker):
        # Arrange
        mock_stdout = mocker.patch("pigit.tui.console._stdout")

        # Act
        Cursor.to(row, col)

        # Assert
        mock_stdout.assert_called_once_with(expected)

    # Test for Cursor.right method
    @pytest.mark.parametrize(
        "dx, expected",
        [
            (1, "\033[1C"),  # Test with minimum value
            (100, "\033[100C"),  # Test with large value
            (0, "\033[0C"),  # Test with zero value
        ],
        ids=["min-value", "large-value", "zero-value"],
    )
    def test_right(self, dx, expected, mocker):
        mock_stdout = mocker.patch("pigit.tui.console._stdout")
        Cursor.right(dx)
        mock_stdout.assert_called_once_with(expected)

    # Test for Cursor.left method
    @pytest.mark.parametrize(
        "dx, expected",
        [
            (1, "\033[1D"),  # Test with minimum value
            (100, "\033[100D"),  # Test with large value
            (0, "\033[0D"),  # Test with zero value
        ],
        ids=["min-value", "large-value", "zero-value"],
    )
    def test_left(self, dx, expected, mocker):
        mock_stdout = mocker.patch("pigit.tui.console._stdout")
        Cursor.left(dx)
        mock_stdout.assert_called_once_with(expected)

    # Test for Cursor.up method
    @pytest.mark.parametrize(
        "dy, expected",
        [
            (1, "\033[1A"),  # Test with minimum value
            (100, "\033[100A"),  # Test with large value
            (0, "\033[0A"),  # Test with zero value
        ],
        ids=["min-value", "large-value", "zero-value"],
    )
    def test_up(self, dy, expected, mocker):
        mock_stdout = mocker.patch("pigit.tui.console._stdout")
        Cursor.up(dy)
        mock_stdout.assert_called_once_with(expected)

    # Test for Cursor.down method
    @pytest.mark.parametrize(
        "dy, expected",
        [
            (1, "\033[1B"),  # Test with minimum value
            (100, "\033[100B"),  # Test with large value
            (0, "\033[0B"),  # Test with zero value
        ],
        ids=["min-value", "large-value", "zero-value"],
    )
    def test_down(self, dy, expected, mocker):
        mock_stdout = mocker.patch("pigit.tui.console._stdout")
        Cursor.down(dy)
        mock_stdout.assert_called_once_with(expected)

    # Test for Cursor.hide_cursor method
    def test_hide_cursor(self, mocker):
        mock_print = mocker.patch("builtins.print")
        Cursor.hide_cursor()
        mock_print.assert_called_once_with("\033[?25l", end="")

    # Test for Cursor.show_cursor method
    def test_show_cursor(self, mocker):
        # Arrange
        mock_print = mocker.patch("builtins.print")
        Cursor.show_cursor()
        mock_print.assert_called_once_with("\033[?25h", end="")
