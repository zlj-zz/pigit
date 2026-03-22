import signal
import termios
import pytest
from unittest.mock import Mock, patch

import pigit.tui
from pigit.tui.input import (
    PosixInput,
    KeyQueueTrie,
    MoreInputRequired,
    process_key_queue,
    process_one_code,
    set_byte_encoding,
    set_encoding,
)


@pytest.mark.parametrize(
    "encoding, expected_byte_encoding, expected_dec_special, expected_target_encoding",
    [
        # Happy path tests
        ("utf-8", "utf8", False, "utf-8"),
        ("UTF8", "utf8", False, "utf8"),
        ("utf", "utf8", False, "utf"),
        ("ascii", "narrow", True, "ascii"),
        ("ISO-8859-1", "narrow", True, "iso-8859-1"),
        # Edge cases
        ("", "narrow", True, "ascii"),
        # Error cases are not applicable as the function handles all strings without raising exceptions
    ],
)
def test_set_encoding(
    encoding,
    expected_byte_encoding,
    expected_dec_special,
    expected_target_encoding,
    mocker,
):
    # Arrange
    mocker.patch("pigit.tui.input.set_byte_encoding")
    mocker.patch("pigit.tui.input._target_encoding", "ascii")
    mocker.patch("pigit.tui.input._use_dec_special", True)

    # Act
    set_encoding(encoding)

    # Assert
    pigit.tui.input.set_byte_encoding.assert_called_with(expected_byte_encoding)
    assert pigit.tui.input._use_dec_special == expected_dec_special
    assert pigit.tui.input._target_encoding == expected_target_encoding


class TestKeyQueueTrie:
    # Test for __init__ and add methods
    @pytest.mark.parametrize(
        "sequences, expected_data",
        [
            (
                (("abc", "result"),),
                {ord("a"): {ord("b"): {ord("c"): "result"}}},
            ),  # Test with single sequence
            (
                (("abc", "result1"), ("def", "result2")),
                {
                    ord("a"): {ord("b"): {ord("c"): "result1"}},
                    ord("d"): {ord("e"): {ord("f"): "result2"}},
                },
            ),  # Test with multiple sequences
        ],
        ids=["single_sequence", "multiple_sequences"],
    )
    def test_init_and_add(self, sequences, expected_data):
        # Arrange
        # Act
        kqt = KeyQueueTrie(sequences)

        # Assert
        assert kqt.data == expected_data

    # Test for get method
    @pytest.mark.parametrize(
        "sequences, codes, more_available, expected",
        [
            (
                (("abc", "value"),),
                [ord("a"), ord("b"), ord("c")],
                False,
                ("value", []),
            ),  # Test case ID: 5
        ],
    )
    def test_get(self, sequences, codes, more_available, expected):
        kqt = KeyQueueTrie(sequences)
        assert kqt.get(codes, more_available) == expected

    @pytest.mark.parametrize(
        "sequences, codes, more_available, expected",
        [
            (
                (("abc", "value"),),
                [ord("a"), ord("b")],
                True,
                MoreInputRequired,
            ),  # Test case ID: 6
        ],
    )
    def test_get_with_more(self, sequences, codes, more_available, expected):
        kqt = KeyQueueTrie(sequences)

        with pytest.raises(expected):
            kqt.get(codes, more_available)

    # Test for get_recurse method
    @pytest.mark.parametrize(
        "sequences, codes, more_available, expected",
        [
            (
                (("abc", "value"),),
                [ord("a"), ord("b"), ord("c")],
                False,
                ("value", []),
            ),  # Test case ID: 7
            (
                (("abc", "value"),),
                [ord("a"), ord("b")],
                True,
                MoreInputRequired,
            ),  # Test case ID: 8
        ],
    )
    def test_get_recurse(self, sequences, codes, more_available, expected):
        # Arrange
        kqt = KeyQueueTrie(sequences)

        # Act & Assert
        if isinstance(expected, type) and issubclass(expected, Exception):
            with pytest.raises(expected):
                kqt.get_recurse(kqt.data, codes, more_available)
        else:
            assert kqt.get_recurse(kqt.data, codes, more_available) == expected

    # Test for read_mouse_info method
    @pytest.mark.parametrize(
        "codes, more_available, expected",
        [
            ([32, 33, 33], False, (("mouse press", 1, 0, 0), [])),  # Test case ID: 9
            ([32, 33], True, MoreInputRequired),  # Test case ID: 10
        ],
    )
    def test_read_mouse_info(self, codes, more_available, expected):
        # Arrange
        kqt = KeyQueueTrie({})

        # Act & Assert
        if isinstance(expected, type) and issubclass(expected, Exception):
            with pytest.raises(expected):
                kqt.read_mouse_info(codes, more_available)
        else:
            assert kqt.read_mouse_info(codes, more_available) == expected

    # Test for read_sgrmouse_info method
    @pytest.mark.parametrize(
        "codes, more_available, expected",
        [
            (
                [ord("0"), ord(";"), ord("1"), ord(";"), ord("1"), ord("M")],
                False,
                (("mouse press", 1, 0, 0), []),
            ),  # Test case ID: 11
            (
                [ord("0"), ord(";"), ord("1"), ord(";"), ord("1")],
                True,
                MoreInputRequired,
            ),  # Test case ID: 12
        ],
    )
    def test_read_sgrmouse_info(self, codes, more_available, expected):
        # Arrange
        kqt = KeyQueueTrie({})

        # Act & Assert
        if isinstance(expected, type) and issubclass(expected, Exception):
            with pytest.raises(expected):
                kqt.read_sgrmouse_info(codes, more_available)
        else:
            assert kqt.read_sgrmouse_info(codes, more_available) == expected

    # Test for read_cursor_position method
    @pytest.mark.parametrize(
        "codes, more_available, expected",
        [
            (
                [ord("["), ord("1"), ord(";"), ord("1"), ord("R")],
                False,
                (("cursor position", 0, 0), []),
            ),  # Test case ID: 13
            (
                [ord("["), ord("1"), ord(";"), ord("1")],
                True,
                MoreInputRequired,
            ),  # Test case ID: 14
        ],
    )
    def test_read_cursor_position(self, codes, more_available, expected):
        # Arrange
        kqt = KeyQueueTrie({})

        # Act & Assert
        if isinstance(expected, type) and issubclass(expected, Exception):
            with pytest.raises(expected):
                kqt.read_cursor_position(codes, more_available)
        else:
            assert kqt.read_cursor_position(codes, more_available) == expected


@pytest.mark.parametrize(
    "code, expected",
    [
        (1, "ctrl a"),  # Lower bound of first if condition
        (26, "ctrl z"),  # Upper bound of first if condition
        (28, "ctrl \\"),  # Lower bound of second if condition
        (31, "ctrl _"),  # Upper bound of second if condition
        (32, " "),  # Lower bound of third if condition
        (126, "~"),  # Upper bound of third if condition
        (10, "enter"),  # Code in _key_conv
        (127, "backspace"),  # Code in _key_conv
        (128, None),  # Code not in _key_conv
        (0, None),  # Code less than 1
    ],
    ids=[
        "ctrl_a",
        "ctrl_z",
        "ctrl_B",
        "ctrl_E",
        "space",
        "tilde",
        "enter",
        "backspace",
        "128",
        "0",
    ],
)
def test_process_one_code(code, expected):
    result = process_one_code(code)
    assert result == expected


# Define a fixture for the MoreInputRequired exception
@pytest.fixture
def more_input_required():
    return MoreInputRequired()


# Define the test function
@pytest.mark.parametrize(
    "codes, more_available, expected_output, expected_remaining_codes",
    [
        # Happy path tests
        ([65, 66, 67], False, ["A"], [66, 67]),  # ID: ASCII codes
        ([27, 65], False, ["meta A"], []),  # ID: ESC code
        ([27, 27, 65], False, ["esc", "meta A"], []),  # ID: Multiple ESC codes
        # Edge cases
        ([], False, [], []),  # ID: Empty codes
        ([32, 126], False, [" "], [126]),  # ID: Boundary ASCII codes
    ],
)
def test_process_key_queue(
    codes, more_available, expected_output, expected_remaining_codes
):
    output, remaining_codes = process_key_queue(codes, more_available)

    # Assert
    assert output == expected_output
    assert remaining_codes == expected_remaining_codes


def test_process_key_queue_with_exception():
    with pytest.raises(MoreInputRequired):
        set_byte_encoding("utf8")
        output, remaining_codes = process_key_queue([240, 201], True)


class TestPosixInput:
    # Test for PosixInput.write method
    @pytest.mark.parametrize(
        "data, id",
        [
            ("Hello World", "happy_path"),
            ("", "empty_string"),
        ],
    )
    def test_write(self, data, id):
        # Arrange
        mock_output = Mock()
        posix_input = PosixInput(output=mock_output)

        # Act
        posix_input.write(data)

        # Assert
        mock_output.write.assert_called_once_with(data)

    # Test for PosixInput.flush method
    def test_flush(self):
        # Arrange
        mock_output = Mock()
        posix_input = PosixInput(output=mock_output)

        # Act
        posix_input.flush()

        # Assert
        mock_output.flush.assert_called_once()

    # Test for PosixInput._input_fileno method
    @pytest.mark.parametrize(
        "has_fileno, expected, id",
        [
            (True, 1, "has_fileno"),
            (False, None, "no_fileno"),
        ],
    )
    def test_input_fileno(self, has_fileno, expected, id):
        # Arrange
        mock_input = Mock()
        if has_fileno:
            mock_input.fileno.return_value = 1
        else:
            del mock_input.fileno
        posix_input = PosixInput(input=mock_input)

        # Act
        result = posix_input._input_fileno()

        # Assert
        assert result == expected

    # Test for PosixInput.set_input_timeouts method
    @pytest.mark.parametrize(
        "max_wait, expected, id",
        [
            (None, None, "max_wait_none"),
            (1.0, 1.0, "max_wait_float"),
        ],
    )
    def test_set_input_timeouts(self, max_wait, expected, id):
        # Arrange
        posix_input = PosixInput()

        # Act
        posix_input.set_input_timeouts(max_wait=max_wait)

        # Assert
        assert posix_input._next_timeout == expected

    # Test for PosixInput._sigwinch_handler method
    def test_sigwinch_handler(self):
        # Arrange
        posix_input = PosixInput()
        posix_input._resized = False

        # Act
        posix_input._sigwinch_handler(None)

        # Assert
        assert posix_input._resized

    # Test for PosixInput.signal_init method
    def test_signal_init(self):
        # Arrange
        mock_signal = Mock()
        posix_input = PosixInput()
        posix_input.signal_handler_setter = mock_signal

        # Act
        posix_input.signal_init()

        # Assert
        mock_signal.assert_called_once_with(
            signal.SIGWINCH, posix_input._sigwinch_handler
        )

    # Test for PosixInput.signal_restore method
    def test_signal_restore(self):
        # Arrange
        mock_signal = Mock()
        posix_input = PosixInput()
        posix_input.signal_handler_setter = mock_signal

        # Act
        posix_input.signal_restore()

        # Assert
        mock_signal.assert_called_once_with(signal.SIGCONT, signal.SIG_DFL)

    # Test for PosixInput.set_mouse_tracking method
    @pytest.mark.parametrize(
        "enable, expected, id",
        [
            (True, True, "enable_true"),
            (False, False, "enable_false"),
        ],
    )
    def test_set_mouse_tracking(self, enable, expected, id):
        # Arrange
        posix_input = PosixInput()
        posix_input._mouse_tracking = Mock()

        # Act
        posix_input.set_mouse_tracking(enable=enable)

        # Assert
        assert posix_input._mouse_tracking_enabled == expected
        enable and posix_input._mouse_tracking.assert_called_once_with(enable)

    # Test for PosixInput.start method
    @patch("os.isatty", return_value=True)
    @patch(
        "termios.tcgetattr",
        return_value=[
            27394,
            3,
            19200,
            536872399,
            38400,
            38400,
            [
                b"\x04",
                b"\xff",
                b"\xff",
                b"\x7f",
                b"\x17",
                b"\x15",
                b"\x12",
                b"\x00",
                b"\x03",
                b"\x1c",
                b"\x1a",
                b"\x19",
                b"\x11",
                b"\x13",
                b"\x16",
                b"\x0f",
                b"\x01",
                b"\x00",
                b"\x14",
                b"\x00",
            ],
        ],
    )
    @patch("tty.setcbreak")
    def test_start(self, mock_setcbreak, mock_tcgetattr, mock_isatty):
        # Arrange
        mock_input = Mock()
        mock_input.fileno.return_value = 1
        posix_input = PosixInput(input=mock_input)
        posix_input.signal_init = Mock()
        posix_input._mouse_tracking = Mock()

        # Act
        posix_input.start()

        # Assert
        mock_isatty.assert_called_with(1)
        mock_tcgetattr.assert_called_with(1)
        mock_setcbreak.assert_called_once_with(1)
        posix_input.signal_init.assert_called_once()
        posix_input._mouse_tracking.assert_called_once_with(
            posix_input._mouse_tracking_enabled
        )

    # Test for PosixInput.stop method
    @patch("os.isatty", return_value=True)
    @patch("termios.tcsetattr")
    def test_stop(self, mock_tcsetattr, mock_isatty):
        # Arrange
        mock_input = Mock()
        mock_input.fileno.return_value = 1
        posix_input = PosixInput(input=mock_input)
        posix_input.signal_restore = Mock()
        posix_input._mouse_tracking = Mock()
        posix_input._old_termios_settings = "old_termios_settings"

        # Act
        posix_input.stop()

        # Assert
        mock_isatty.assert_called_once_with(1)
        mock_tcsetattr.assert_called_once_with(
            1, termios.TCSADRAIN, "old_termios_settings"
        )
        posix_input.signal_restore.assert_called_once()
        posix_input._mouse_tracking.assert_called_once_with(False)

    # Test for PosixInput._wait_input_ready method
    @patch("select.select", return_value=([1], [], []))
    def test_wait_input_ready(self, mock_select):
        # Arrange
        mock_input = Mock()
        mock_input.fileno.return_value = 1
        posix_input = PosixInput(input=mock_input)

        # Act
        result = posix_input._wait_input_ready(1.0)

        # Assert
        mock_select.assert_called_once_with([1], [], [1], 1.0)
        assert result == [1]

    # Test for PosixInput._getch method
    @patch("os.read", return_value=b"a")
    def test_getch(self, mock_read):
        # Arrange
        mock_input = Mock()
        mock_input.fileno.return_value = 1
        posix_input = PosixInput(input=mock_input)
        posix_input._wait_input_ready = Mock(return_value=[1])

        # Act
        result = posix_input._getch(1.0)

        # Assert
        posix_input._wait_input_ready.assert_called_once_with(1.0)
        mock_read.assert_called_once_with(1, 1)
        assert result == ord("a")

    # Test for PosixInput._getch_no_delay method
    @patch("os.read", return_value=b"a")
    def test_getch_no_delay(self, mock_read):
        # Arrange
        mock_input = Mock()
        mock_input.fileno.return_value = 1
        posix_input = PosixInput(input=mock_input)
        posix_input._wait_input_ready = Mock(return_value=[1])

        # Act
        result = posix_input._getch_no_delay()

        # Assert
        posix_input._wait_input_ready.assert_called_once_with(0)
        mock_read.assert_called_once_with(1, 1)
        assert result == ord("a")

    # Test for PosixInput._get_keyboard_codes method
    # @patch("os.read", return_value=b"a")
    # def test_get_keyboard_codes(mock_read):
    #     # Arrange
    #     mock_input = Mock()
    #     mock_input.fileno.return_value = 1
    #     posix_input = PosixInput(input=mock_input)
    #     posix_input._wait_input_ready = Mock(return_value=[1])

    #     # Act
    #     result = posix_input._get_keyboard_codes()

    #     # Assert
    #     posix_input._wait_input_ready.assert_called_once_with(0)
    #     mock_read.assert_called_once_with(1, 1)
    #     assert result == [ord("a")]

    # Test for PosixInput.get_available_raw_input method
    def test_get_available_raw_input(self):
        # Arrange
        posix_input = PosixInput()
        posix_input._get_gpm_codes = Mock(return_value=[1])
        posix_input._get_keyboard_codes = Mock(return_value=[2])
        posix_input._partial_codes = [3]

        # Act
        result = posix_input.get_available_raw_input()

        # Assert
        posix_input._get_gpm_codes.assert_called_once()
        posix_input._get_keyboard_codes.assert_called_once()
        assert result == [3, 1, 2]
        assert posix_input._partial_codes is None

    # Test for PosixInput.get_input method
    def test_get_input(self):
        # Arrange
        posix_input = PosixInput()
        posix_input._wait_input_ready = Mock()
        posix_input.get_available_raw_input = Mock(return_value=[1])
        posix_input.parse_input = Mock(return_value=(["a"], [1]))

        # Act
        result = posix_input.get_input(raw_keys=True)

        # Assert
        posix_input._wait_input_ready.assert_called_once_with(posix_input._next_timeout)
        posix_input.get_available_raw_input.assert_called_once()
        posix_input.parse_input.assert_called_once_with(None, [1])
        assert result == (["a"], [1])
