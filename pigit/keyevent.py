# -*- coding:utf-8 -*-

import os
import sys
import signal
from typing import Optional, Type

# try to import needed pkg.
# If import failed, set `TERM_CONTROL` is False.
TERM_CONTROL = True
NEED_EXTRA_KEYBOARD_EVENT_PKG = False
try:
    import select, termios, fcntl, tty  # noqa: E401

    B = lambda x: x.encode("iso8859-1")  # noqa: E731
except Exception:
    try:
        from pynput import keyboard  # type: ignore

        import queue

        NEED_EXTRA_KEYBOARD_EVENT_PKG = True
    except ModuleNotFoundError:
        TERM_CONTROL = False
        print("Please install `pynput` to supported keyboard event.")


class _baseKeyEvent(object):
    def signal_init(self) -> ...:
        """Take over the system signal, which is implemented by subclasses."""
        raise NotImplementedError()

    def signal_restore(self) -> ...:
        """Reply signal, implemented by subclass."""
        raise NotImplementedError()

    def sync_get_input(self) -> ...:
        raise NotImplementedError()


#####################################################################
# KeyBoard event classes.                                           #
#####################################################################
class _PosixKeyEvent(_baseKeyEvent):
    """KeyBoard event class.

    Subclass:
        Raw: Set raw input mode for device.
        Nonblocking: Set nonblocking mode for device.

    Attributes:
        escape: Translation dictionary.
        _resized: windows resize handle.

    Functions:
        signal_init: Register signal events.
        signal_restore: Unregister signal events.
        sync_get_key: get one input value, will wait until get input.
    """

    class Raw(object):
        """Set raw input mode for device"""

        def __init__(self, stream):
            self.stream = stream
            self.fd = self.stream.fileno()

        def __enter__(self):
            # Get original fd descriptor.
            self.original_descriptor = termios.tcgetattr(self.stream)
            # Change the mode of the file descriptor fd to cbreak.
            tty.setcbreak(self.stream)

        def __exit__(self, type, value, traceback):
            termios.tcsetattr(self.stream, termios.TCSANOW, self.original_descriptor)

    class Nonblocking(object):
        """Set nonblocking mode for device"""

        def __init__(self, stream):
            self.stream = stream
            self.fd = self.stream.fileno()

        def __enter__(self):
            self.orig_fl = fcntl.fcntl(self.fd, fcntl.F_GETFL)
            fcntl.fcntl(self.fd, fcntl.F_SETFL, self.orig_fl | os.O_NONBLOCK)

        def __exit__(self, *args):
            fcntl.fcntl(self.fd, fcntl.F_SETFL, self.orig_fl)

    escape = {
        "\n": "enter",
        ("\x7f", "\x08"): "backspace",
        ("[A", "OA"): "up",
        ("[B", "OB"): "down",
        ("[D", "OD"): "left",
        ("[C", "OC"): "right",
        "[2~": "insert",
        "[3~": "delete",
        "[H": "home",
        "[F": "end",
        "[5~": "page_up",
        "[6~": "page_down",
        "\t": "tab",
        "[Z": "shift_tab",
        "OP": "f1",
        "OQ": "f2",
        "OR": "f3",
        "OS": "f4",
        "[15": "f5",
        "[17": "f6",
        "[18": "f7",
        "[19": "f8",
        "[20": "f9",
        "[21": "f10",
        "[23": "f11",
        "[24": "f12",
        " ": "space",
    }

    _resize_pipe_rd, _resize_pipe_wr = os.pipe()
    _resized = False

    @classmethod
    def _sigwinch_handler(cls, signum, frame=None):
        if not cls._resized:
            os.write(cls._resize_pipe_wr, B("R"))
        cls._resized = True

    @classmethod
    def signal_init(cls):
        signal.signal(signal.SIGWINCH, cls._sigwinch_handler)

    @classmethod
    def signal_restore(cls):
        signal.signal(signal.SIGWINCH, signal.SIG_DFL)

    @classmethod
    def sync_get_input(cls):
        while True:
            with cls.Raw(sys.stdin):
                if cls._resized:
                    cls._resized = False
                    clean_key = "windows resize"
                    return clean_key

                # * Wait 100ms for input on stdin then restart loop to check for stop flag
                if not select.select([sys.stdin], [], [], 0.1)[0]:
                    continue
                input_key = sys.stdin.read(1)
                if input_key == "\033":
                    # * Set non blocking to prevent read stall
                    with cls.Nonblocking(sys.stdin):
                        input_key += sys.stdin.read(20)
                        if input_key.startswith("\033[<"):
                            _ = sys.stdin.read(1000)
                # print(repr(input_key))
                if input_key == "\033":
                    clean_key = "escape"
                elif input_key == "\\":
                    clean_key = "\\"  # * Clean up "\" to not return escaped
                else:
                    for code in cls.escape:
                        if input_key.lstrip("\033").startswith(code):
                            clean_key = cls.escape[code]
                            break
                    else:
                        clean_key = input_key

                # print(clean_key)
                return clean_key


class _WinKeyEvent(_baseKeyEvent):
    _special_keys = {
        "Key.space": "space",
        "Key.up": "up",
        "Key.down": "down",
        "Key.esc": "escape",
        "Key.enter": "enter",
    }

    def __init__(self):
        super(_WinKeyEvent, self).__init__()
        self._queue = queue.Queue(maxsize=1)
        self.listener = keyboard.Listener(on_press=self._on_press, suppress=True)
        self.listener.start()

    def _on_press(self, key):
        # process and push to queue

        self._queue.put(key)

    def signal_init(self) -> ...:
        pass

    def signal_restore(self) -> ...:
        pass

    def sync_get_input(self):
        resp = str(self._queue.get(block=True, timeout=None)).strip("'")
        if resp in self._special_keys:
            return self._special_keys[resp]
        else:
            return resp


def get_keyevent_obj() -> Type[_baseKeyEvent]:
    """Keyevent Object Factory."""
    if not TERM_CONTROL:
        raise NameError("Can't get right class.")
    if not NEED_EXTRA_KEYBOARD_EVENT_PKG:
        keyevent = _PosixKeyEvent
    else:
        keyevent = _WinKeyEvent
    return keyevent
