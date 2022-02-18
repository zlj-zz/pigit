# -*- coding:utf-8 -*-

import ctypes
from ctypes import windll, wintypes

import threading
import six
import queue
import functools


# LPDWORD is not in ctypes.wintypes on Python 2
if not hasattr(wintypes, "LPDWORD"):
    wintypes.LPDWORD = ctypes.POINTER(wintypes.DWORD)


GetCurrentThreadId = windll.kernel32.GetCurrentThreadId
GetCurrentThreadId.restype = wintypes.DWORD


class AbstractListener(threading.Thread):
    """A class implementing the basic behaviour for event listeners.
    Instances of this class can be used as context managers. This is equivalent
    to the following code::
        listener.start()
        listener.wait()
        try:
            with_statements()
        finally:
            listener.stop()
    Actual implementations of this class must set the attribute ``_log``, which
    must be an instance of :class:`logging.Logger`.
    :param bool suppress: Whether to suppress events. Setting this to ``True``
        will prevent the input events from being passed to the rest of the
        system.
    :param kwargs: A mapping from callback attribute to callback handler. All
        handlers will be wrapped in a function reading the return value of the
        callback, and if it ``is False``, raising :class:`StopException`.
        Any callback that is falsy will be ignored.
    """

    class StopException(Exception):
        """If an event listener callback raises this exception, the current
        listener is stopped.
        """

        pass

    #: Exceptions that are handled outside of the emitter and should thus not
    #: be passed through the queue
    _HANDLED_EXCEPTIONS = tuple()

    def __init__(self, suppress=False, **kwargs):
        super(AbstractListener, self).__init__()

        def wrapper(f):
            def inner(*args):
                if f(*args) is False:
                    raise self.StopException()

            return inner

        self._suppress = suppress
        self._running = False
        self._thread = threading.current_thread()
        self._condition = threading.Condition()
        self._ready = False

        # Allow multiple calls to stop
        self._queue = queue.Queue(10)

        self.daemon = True

        for name, callback in kwargs.items():
            setattr(self, name, wrapper(callback or (lambda *a: None)))

    @property
    def suppress(self):
        """Whether to suppress events."""
        return self._suppress

    @property
    def running(self):
        """Whether the listener is currently running."""
        return self._running

    def stop(self):
        """Stops listening for events.
        When this method returns, no more events will be delivered. Once this
        method has been called, the listener instance cannot be used any more,
        since a listener is a :class:`threading.Thread`, and once stopped it
        cannot be restarted.
        To resume listening for event, a new listener must be created.
        """
        if self._running:
            self._running = False
            self._queue.put(None)
            self._stop_platform()

    def __enter__(self):
        self.start()
        self.wait()
        return self

    def __exit__(self, exc_type, value, traceback):
        self.stop()

    def wait(self):
        """Waits for this listener to become ready."""
        self._condition.acquire()
        while not self._ready:
            self._condition.wait()
        self._condition.release()

    def run(self):
        """The thread runner method."""
        self._running = True
        self._thread = threading.current_thread()
        self._run()

        # Make sure that the queue contains something
        self._queue.put(None)

    @classmethod
    def _emitter(cls, f):
        """A decorator to mark a method as the one emitting the callbacks.
        This decorator will wrap the method and catch exception. If a
        :class:`StopException` is caught, the listener will be stopped
        gracefully. If any other exception is caught, it will be propagated to
        the thread calling :meth:`join` and reraised there.
        """

        @functools.wraps(f)
        def inner(self, *args, **kwargs):
            # pylint: disable=W0702; we want to catch all exception
            try:
                return f(self, *args, **kwargs)
            except Exception as e:
                if not isinstance(e, self._HANDLED_EXCEPTIONS):
                    if not isinstance(e, AbstractListener.StopException):
                        self._log.exception("Unhandled exception in listener callback")
                    self._queue.put(
                        None if isinstance(e, cls.StopException) else sys.exc_info()
                    )
                    self.stop()
                raise
            # pylint: enable=W0702

        return inner

    def _mark_ready(self):
        """Marks this listener as ready to receive events.
        This method must be called from :meth:`_run`. :meth:`wait` will block
        until this method is called.
        """
        self._condition.acquire()
        self._ready = True
        self._condition.notify()
        self._condition.release()

    def _run(self):
        """The implementation of the :meth:`run` method.
        This is a platform dependent implementation.
        """
        raise NotImplementedError()

    def _stop_platform(self):
        """The implementation of the :meth:`stop` method.
        This is a platform dependent implementation.
        """
        raise NotImplementedError()

    def join(self, *args):
        super(AbstractListener, self).join(*args)

        # Reraise any exceptions
        try:
            exc_type, exc_value, exc_traceback = self._queue.get()
        except TypeError:
            return
        six.reraise(exc_type, exc_value, exc_traceback)


class _Listener(AbstractListener):
    """A listener for keyboard events.
    Instances of this class can be used as context managers. This is equivalent
    to the following code::
        listener.start()
        try:
            listener.wait()
            with_statements()
        finally:
            listener.stop()
    This class inherits from :class:`threading.Thread` and supports all its
    methods. It will set :attr:`daemon` to ``True`` when created.
    :param callable on_press: The callback to call when a button is pressed.
        It will be called with the argument ``(key)``, where ``key`` is a
        :class:`KeyCode`, a :class:`Key` or ``None`` if the key is unknown.
    :param callable on_release: The callback to call when a button is released.
        It will be called with the argument ``(key)``, where ``key`` is a
        :class:`KeyCode`, a :class:`Key` or ``None`` if the key is unknown.
    :param bool suppress: Whether to suppress events. Setting this to ``True``
        will prevent the input events from being passed to the rest of the
        system.
    :param kwargs: Any non-standard platform dependent options. These should be
        prefixed with the platform name thus: ``darwin_``, ``xorg_`` or
        ``win32_``.
        Supported values are:
        ``darwin_intercept``
            A callable taking the arguments ``(event_type, event)``, where
            ``event_type`` is ``Quartz.kCGEventKeyDown`` or
            ``Quartz.kCGEventKeyDown``, and ``event`` is a ``CGEventRef``.
            This callable can freely modify the event using functions like
            ``Quartz.CGEventSetIntegerValueField``. If this callable does not
            return the event, the event is suppressed system wide.
        ``win32_event_filter``
            A callable taking the arguments ``(msg, data)``, where ``msg`` is
            the current message, and ``data`` associated data as a
            `KBDLLHOOKSTRUCT <https://docs.microsoft.com/en-gb/windows/win32/api/winuser/ns-winuser-kbdllhookstruct>`_.
            If this callback returns ``False``, the event will not be
            propagated to the listener callback.
            If ``self.suppress_event()`` is called, the event is suppressed
            system wide.
    """

    def __init__(self, on_press=None, on_release=None, suppress=False, **kwargs):
        prefix = self.__class__.__module__.rsplit(".", 1)[-1][1:] + "_"
        self._options = {
            key[len(prefix) :]: value
            for key, value in kwargs.items()
            if key.startswith(prefix)
        }
        super(_Listener, self).__init__(
            on_press=on_press, on_release=on_release, suppress=suppress
        )

    # pylint: enable=W0223

    def canonical(self, key):
        """Performs normalisation of a key.
        This method attempts to convert key events to their canonical form, so
        that events will equal regardless of modifier state.
        This method will convert upper case keys to lower case keys, convert
        any modifiers with a right and left version to the same value, and may
        slow perform additional platform dependent normalisation.
        :param key: The key to normalise.
        :type key: Key or KeyCode
        :return: a key
        :rtype: Key or KeyCode
        """
        from pynput.keyboard import Key, KeyCode, _NORMAL_MODIFIERS

        if isinstance(key, KeyCode) and key.char is not None:
            return KeyCode.from_char(key.char.lower())
        elif isinstance(key, Key) and key.value in _NORMAL_MODIFIERS:
            return _NORMAL_MODIFIERS[key.value]
        else:
            return key


class MessageLoop(object):
    """A class representing a message loop."""

    #: The message that signals this loop to terminate
    WM_STOP = 0x0401

    _LPMSG = ctypes.POINTER(wintypes.MSG)

    _GetMessage = windll.user32.GetMessageW
    _GetMessage.argtypes = (
        ctypes.c_voidp,  # Really _LPMSG
        wintypes.HWND,
        wintypes.UINT,
        wintypes.UINT,
    )
    _PeekMessage = windll.user32.PeekMessageW
    _PeekMessage.argtypes = (
        ctypes.c_voidp,  # Really _LPMSG
        wintypes.HWND,
        wintypes.UINT,
        wintypes.UINT,
        wintypes.UINT,
    )
    _PostThreadMessage = windll.user32.PostThreadMessageW
    _PostThreadMessage.argtypes = (
        wintypes.DWORD,
        wintypes.UINT,
        wintypes.WPARAM,
        wintypes.LPARAM,
    )

    PM_NOREMOVE = 0

    def __init__(self):
        self._threadid = None
        self._event = threading.Event()
        self.thread = None

    def __iter__(self):
        """Initialises the message loop and yields all messages until
        :meth:`stop` is called.
        :raises AssertionError: if :meth:`start` has not been called
        """
        assert self._threadid is not None

        try:
            # Pump messages until WM_STOP
            while True:
                msg = wintypes.MSG()
                lpmsg = ctypes.byref(msg)
                r = self._GetMessage(lpmsg, None, 0, 0)
                if r <= 0 or msg.message == self.WM_STOP:
                    break
                else:
                    yield msg

        finally:
            self._threadid = None
            self.thread = None

    def start(self):
        """Starts the message loop.
        This method must be called before iterating over messages, and it must
        be called from the same thread.
        """
        self._threadid = GetCurrentThreadId()
        self.thread = threading.current_thread()

        # Create the message loop
        msg = wintypes.MSG()
        lpmsg = ctypes.byref(msg)
        self._PeekMessage(lpmsg, None, 0x0400, 0x0400, self.PM_NOREMOVE)

        # Set the event to signal to other threads that the loop is created
        self._event.set()

    def stop(self):
        """Stops the message loop."""
        self._event.wait()
        if self._threadid:
            self.post(self.WM_STOP, 0, 0)

    def post(self, msg, wparam, lparam):
        """Posts a message to this message loop.
        :param ctypes.wintypes.UINT msg: The message.
        :param ctypes.wintypes.WPARAM wparam: The value of ``wParam``.
        :param ctypes.wintypes.LPARAM lparam: The value of ``lParam``.
        """
        self._PostThreadMessage(self._threadid, msg, wparam, lparam)


class SystemHook(object):
    """A class to handle Windows hooks."""

    #: The hook action value for actions we should check
    HC_ACTION = 0

    _HOOKPROC = ctypes.WINFUNCTYPE(
        wintypes.LPARAM, ctypes.c_int32, wintypes.WPARAM, wintypes.LPARAM
    )

    _SetWindowsHookEx = windll.user32.SetWindowsHookExW
    _SetWindowsHookEx.argtypes = (
        ctypes.c_int,
        _HOOKPROC,
        wintypes.HINSTANCE,
        wintypes.DWORD,
    )
    _UnhookWindowsHookEx = windll.user32.UnhookWindowsHookEx
    _UnhookWindowsHookEx.argtypes = (wintypes.HHOOK,)
    _CallNextHookEx = windll.user32.CallNextHookEx
    _CallNextHookEx.argtypes = (
        wintypes.HHOOK,
        ctypes.c_int,
        wintypes.WPARAM,
        wintypes.LPARAM,
    )

    #: The registered hook procedures
    _HOOKS = {}

    class SuppressException(Exception):
        """An exception raised by a hook callback to suppress further
        propagation of events.
        """

        pass

    def __init__(self, hook_id, on_hook=lambda code, msg, lpdata: None):
        self.hook_id = hook_id
        self.on_hook = on_hook
        self._hook = None

    def __enter__(self):
        key = threading.current_thread().ident
        assert key not in self._HOOKS

        # Add ourself to lookup table and install the hook
        self._HOOKS[key] = self
        self._hook = self._SetWindowsHookEx(self.hook_id, self._handler, None, 0)

        return self

    def __exit__(self, exc_type, value, traceback):
        key = threading.current_thread().ident
        assert key in self._HOOKS

        if self._hook is not None:
            # Uninstall the hook and remove ourself from lookup table
            self._UnhookWindowsHookEx(self._hook)
            del self._HOOKS[key]

    @staticmethod
    @_HOOKPROC
    def _handler(code, msg, lpdata):
        key = threading.current_thread().ident
        self = SystemHook._HOOKS.get(key, None)
        if self:
            # pylint: disable=W0702; we want to silence errors
            try:
                self.on_hook(code, msg, lpdata)
            except self.SuppressException:
                # Return non-zero to stop event propagation
                return 1
            except:
                # Ignore any errors
                pass
            # pylint: enable=W0702
            return SystemHook._CallNextHookEx(0, code, msg, lpdata)


class ListenerMixin(object):
    """A mixin for *win32* event listeners.
    Subclasses should set a value for :attr:`_EVENTS` and implement
    :meth:`_handle`.
    Subclasses must also be decorated with a decorator compatible with
    :meth:`pynput._util.NotifierMixin._receiver` or implement the method
    ``_receive()``.
    """

    #: The Windows hook ID for the events to capture.
    _EVENTS = None

    #: The window message used to signal that an even should be handled.
    _WM_PROCESS = 0x410

    #: Additional window messages to propagate to the subclass handler.
    _WM_NOTIFICATIONS = []

    def suppress_event(self):
        """Causes the currently filtered event to be suppressed.
        This has a system wide effect and will generally result in no
        applications receiving the event.
        This method will raise an undefined exception.
        """
        raise SystemHook.SuppressException()

    def _run(self):
        self._message_loop = MessageLoop()
        with self._receive():
            self._mark_ready()
            self._message_loop.start()

            # pylint: disable=W0702; we want to silence errors
            try:
                with SystemHook(self._EVENTS, self._handler):
                    # Just pump messages
                    for msg in self._message_loop:
                        if not self.running:
                            break
                        if msg.message == self._WM_PROCESS:
                            self._process(msg.wParam, msg.lParam)
                        elif msg.message in self._WM_NOTIFICATIONS:
                            self._on_notification(msg.message, msg.wParam, msg.lParam)
            except:
                # This exception will have been passed to the main thread
                pass
            # pylint: enable=W0702

    def _stop_platform(self):
        try:
            self._message_loop.stop()
        except AttributeError:
            # The loop may not have been created
            pass

    @AbstractListener._emitter
    def _handler(self, code, msg, lpdata):
        """The callback registered with *Windows* for events.
        This method will post the message :attr:`_WM_HANDLE` to the message
        loop started with this listener using :meth:`MessageLoop.post`. The
        parameters are retrieved with a call to :meth:`_handle`.
        """
        try:
            converted = self._convert(code, msg, lpdata)
            if converted is not None:
                self._message_loop.post(self._WM_PROCESS, *converted)
        except NotImplementedError:
            self._handle(code, msg, lpdata)

        if self.suppress:
            self.suppress_event()

    def _convert(self, code, msg, lpdata):
        """The device specific callback handler.
        This method converts a low-level message and data to a
        ``WPARAM`` / ``LPARAM`` pair.
        """
        raise NotImplementedError()

    def _process(self, wparam, lparam):
        """The device specific callback handler.
        This method performs the actual dispatching of events.
        """
        raise NotImplementedError()

    def _handle(self, code, msg, lpdata):
        """The device specific callback handler.
        This method calls the appropriate callback registered when this
        listener was created based on the event.
        This method is only called if :meth:`_convert` is not implemented.
        """
        raise NotImplementedError()

    def _on_notification(self, code, wparam, lparam):
        """An additional notification handler.
        This method will be called for every message in
        :attr:`_WM_NOTIFICATIONS`.
        """
        raise NotImplementedError()


class Listener(ListenerMixin, _Listener):
    #: The Windows hook ID for low level keyboard events, ``WH_KEYBOARD_LL``
    _EVENTS = 13

    _WM_INPUTLANGCHANGE = 0x0051
    _WM_KEYDOWN = 0x0100
    _WM_KEYUP = 0x0101
    _WM_SYSKEYDOWN = 0x0104
    _WM_SYSKEYUP = 0x0105

    # A bit flag attached to messages indicating that the payload is an actual
    # UTF-16 character code
    _UTF16_FLAG = 0x1000

    # A special virtual key code designating unicode characters
    _VK_PACKET = 0xE7

    #: The messages that correspond to a key press
    _PRESS_MESSAGES = (_WM_KEYDOWN, _WM_SYSKEYDOWN)

    #: The messages that correspond to a key release
    _RELEASE_MESSAGES = (_WM_KEYUP, _WM_SYSKEYUP)

    #: Additional window messages to propagate to the subclass handler.
    _WM_NOTIFICATIONS = (_WM_INPUTLANGCHANGE,)

    #: A mapping from keysym to special key
    _SPECIAL_KEYS = {key.value.vk: key for key in Key}

    _HANDLED_EXCEPTIONS = (SystemHook.SuppressException,)

    class _KBDLLHOOKSTRUCT(ctypes.Structure):
        """Contains information about a mouse event passed to a
        ``WH_KEYBOARD_LL`` hook procedure, ``LowLevelKeyboardProc``.
        """

        _fields_ = [
            ("vkCode", wintypes.DWORD),
            ("scanCode", wintypes.DWORD),
            ("flags", wintypes.DWORD),
            ("time", wintypes.DWORD),
            ("dwExtraInfo", ctypes.c_void_p),
        ]

    #: A pointer to a :class:`KBDLLHOOKSTRUCT`
    _LPKBDLLHOOKSTRUCT = ctypes.POINTER(_KBDLLHOOKSTRUCT)

    def __init__(self, *args, **kwargs):
        super(Listener, self).__init__(*args, **kwargs)
        self._translator = KeyTranslator()
        self._event_filter = self._options.get("event_filter", lambda msg, data: True)

    def _convert(self, code, msg, lpdata):
        if code != SystemHook.HC_ACTION:
            return

        data = ctypes.cast(lpdata, self._LPKBDLLHOOKSTRUCT).contents
        is_packet = data.vkCode == self._VK_PACKET

        # Suppress further propagation of the event if it is filtered
        if self._event_filter(msg, data) is False:
            return None
        elif is_packet:
            return (msg | self._UTF16_FLAG, data.scanCode)
        else:
            return (msg, data.vkCode)

    @AbstractListener._emitter
    def _process(self, wparam, lparam):
        msg = wparam
        vk = lparam

        # If the key has the UTF-16 flag, we treat it as a unicode character,
        # otherwise convert the event to a KeyCode; this may fail, and in that
        # case we pass None
        is_utf16 = msg & self._UTF16_FLAG
        if is_utf16:
            msg = msg ^ self._UTF16_FLAG
            scan = vk
            key = KeyCode.from_char(six.unichr(scan))
        else:
            try:
                key = self._event_to_key(msg, vk)
            except OSError:
                key = None

        if msg in self._PRESS_MESSAGES:
            self.on_press(key)

        elif msg in self._RELEASE_MESSAGES:
            self.on_release(key)

    # pylint: disable=R0201
    @contextlib.contextmanager
    def _receive(self):
        """An empty context manager; we do not need to fake keyboard events."""
        yield

    # pylint: enable=R0201

    def _on_notification(self, code, wparam, lparam):
        """Receives ``WM_INPUTLANGCHANGE`` and updates the cached layout."""
        if code == self._WM_INPUTLANGCHANGE:
            self._translator.update_layout()

    def _event_to_key(self, msg, vk):
        """Converts an :class:`_KBDLLHOOKSTRUCT` to a :class:`KeyCode`.
        :param msg: The message received.
        :param vk: The virtual key code to convert.
        :return: a :class:`pynput.keyboard.KeyCode`
        :raises OSError: if the message and data could not be converted
        """
        # If the virtual key code corresponds to a Key value, we prefer that
        if vk in self._SPECIAL_KEYS:
            return self._SPECIAL_KEYS[vk]
        else:
            return KeyCode(**self._translate(vk, msg in self._PRESS_MESSAGES))

    def _translate(self, vk, is_press):
        """Translates a virtual key code to a parameter list passable to
        :class:`pynput.keyboard.KeyCode`.
        :param int vk: The virtual key code.
        :param bool is_press: Whether this is a press event.
        :return: a parameter list to the :class:`pynput.keyboard.KeyCode`
            constructor
        """
        return self._translator(vk, is_press)

    def canonical(self, key):
        # If the key has a scan code, and we can find the character for it,
        # return that, otherwise call the super class
        scan = getattr(key, "_scan", None)
        if scan is not None:
            char = self._translator.char_from_scan(scan)
            if char is not None:
                return KeyCode.from_char(char)

        return super(Listener, self).canonical(key)


class WinKeyEvent:
    #: The Windows hook ID for low level keyboard events, ``WH_KEYBOARD_LL``
    _EVENTS = 13

    #: The window message used to signal that an even should be handled.
    _WM_PROCESS = 0x410

    #: Additional window messages to propagate to the subclass handler.
    _WM_NOTIFICATIONS = []

    _WM_INPUTLANGCHANGE = 0x0051
    _WM_KEYDOWN = 0x0100
    _WM_KEYUP = 0x0101
    _WM_SYSKEYDOWN = 0x0104
    _WM_SYSKEYUP = 0x0105

    # A bit flag attached to messages indicating that the payload is an actual
    # UTF-16 character code
    _UTF16_FLAG = 0x1000

    # A special virtual key code designating unicode characters
    _VK_PACKET = 0xE7

    #: The messages that correspond to a key press
    _PRESS_MESSAGES = (_WM_KEYDOWN, _WM_SYSKEYDOWN)

    #: The messages that correspond to a key release
    _RELEASE_MESSAGES = (_WM_KEYUP, _WM_SYSKEYUP)

    #: Additional window messages to propagate to the subclass handler.
    _WM_NOTIFICATIONS = (_WM_INPUTLANGCHANGE,)

    _HANDLED_EXCEPTIONS = (SystemHook.SuppressException,)

    class _KBDLLHOOKSTRUCT(ctypes.Structure):
        """Contains information about a mouse event passed to a
        ``WH_KEYBOARD_LL`` hook procedure, ``LowLevelKeyboardProc``.
        """

        _fields_ = [
            ("vkCode", wintypes.DWORD),
            ("scanCode", wintypes.DWORD),
            ("flags", wintypes.DWORD),
            ("time", wintypes.DWORD),
            ("dwExtraInfo", ctypes.c_void_p),
        ]

    #: A pointer to a :class:`KBDLLHOOKSTRUCT`
    _LPKBDLLHOOKSTRUCT = ctypes.POINTER(_KBDLLHOOKSTRUCT)

    #: A mapping from keysym to special key
    escape = {
        13: "enter",
        8: "backspace",
        37: "left",
        38: "up",
        39: "right",
        40: "down",
        45: "insert",
        46: "delete",
        36: "home",
        35: "end",
        # "[5~": "page_up",
        # "[6~": "page_down",
        9: "tab",
        16: "shift_tab",
        112: "f1",
        113: "f2",
        114: "f3",
        115: "f4",
        116: "f5",
        117: "f6",
        118: "f7",
        119: "f8",
        120: "f9",
        121: "f10",
        122: "f11",
        123: "f12",
        32: "space",
        27: "escape",
    }

    class SystemHook(object):
        """A class to handle Windows hooks."""

        #: The hook action value for actions we should check
        HC_ACTION = 0

        _HOOKPROC = ctypes.WINFUNCTYPE(
            wintypes.LPARAM, ctypes.c_int32, wintypes.WPARAM, wintypes.LPARAM
        )

        _SetWindowsHookEx = windll.user32.SetWindowsHookExW
        _SetWindowsHookEx.argtypes = (
            ctypes.c_int,
            _HOOKPROC,
            wintypes.HINSTANCE,
            wintypes.DWORD,
        )
        _UnhookWindowsHookEx = windll.user32.UnhookWindowsHookEx
        _UnhookWindowsHookEx.argtypes = (wintypes.HHOOK,)
        _CallNextHookEx = windll.user32.CallNextHookEx
        _CallNextHookEx.argtypes = (
            wintypes.HHOOK,
            ctypes.c_int,
            wintypes.WPARAM,
            wintypes.LPARAM,
        )

        #: The registered hook procedures
        _HOOKS = {}

        class SuppressException(Exception):
            """An exception raised by a hook callback to suppress further
            propagation of events.
            """

            pass

        def __init__(self, hook_id, on_hook=lambda code, msg, lpdata: None):
            self.hook_id = hook_id
            self.on_hook = on_hook
            self._hook = None

        def __enter__(self):
            key = threading.current_thread().ident
            assert key not in self._HOOKS

            # Add ourself to lookup table and install the hook
            self._HOOKS[key] = self
            self._hook = self._SetWindowsHookEx(self.hook_id, self._handler, None, 0)

            return self

        def __exit__(self, exc_type, value, traceback):
            key = threading.current_thread().ident
            assert key in self._HOOKS

            if self._hook is not None:
                # Uninstall the hook and remove ourself from lookup table
                self._UnhookWindowsHookEx(self._hook)
                del self._HOOKS[key]

        @staticmethod
        @_HOOKPROC
        def _handler(code, msg, lpdata):
            key = threading.current_thread().ident
            self = SystemHook._HOOKS.get(key, None)
            if self:
                # pylint: disable=W0702; we want to silence errors
                try:
                    self.on_hook(code, msg, lpdata)
                except self.SuppressException:
                    # Return non-zero to stop event propagation
                    return 1
                except:
                    # Ignore any errors
                    pass
                # pylint: enable=W0702
                return SystemHook._CallNextHookEx(0, code, msg, lpdata)

    def __init__(self):
        super(WinKeyEvent, self).__init__()
        pass

    def run(self):
        self._message_loop = MessageLoop()
        with self._receive():
            self._mark_ready()
            self._message_loop.start()

            # pylint: disable=W0702; we want to silence errors
            try:
                with SystemHook(self._EVENTS, self._handler):
                    # Just pump messages
                    for msg in self._message_loop:
                        if msg.message == self._WM_PROCESS:
                            self._process(msg.wParam, msg.lParam)
                        elif msg.message in self._WM_NOTIFICATIONS:
                            self._on_notification(msg.message, msg.wParam, msg.lParam)
            except:
                # This exception will have been passed to the main thread
                pass
            # pylint: enable=W0702

    def _handler(self, code, msg, lpdata):
        """The callback registered with *Windows* for events.
        This method will post the message :attr:`_WM_HANDLE` to the message
        loop started with this listener using :meth:`MessageLoop.post`. The
        parameters are retrieved with a call to :meth:`_handle`.
        """
        try:
            converted = self._convert(code, msg, lpdata)
            if converted is not None:
                self._message_loop.post(self._WM_PROCESS, *converted)
        except NotImplementedError:
            self._handle(code, msg, lpdata)

        if self.suppress:
            self.suppress_event()

    def _convert(self, code, msg, lpdata):
        if code != SystemHook.HC_ACTION:
            return

        data = ctypes.cast(lpdata, self._LPKBDLLHOOKSTRUCT).contents
        is_packet = data.vkCode == self._VK_PACKET

        if is_packet:
            return (msg | self._UTF16_FLAG, data.scanCode)
        else:
            return (msg, data.vkCode)

    def _event_to_key(self, msg, vk):
        """Converts an :class:`_KBDLLHOOKSTRUCT` to a :class:`KeyCode`.
        :param msg: The message received.
        :param vk: The virtual key code to convert.
        :return: a :class:`pynput.keyboard.KeyCode`
        :raises OSError: if the message and data could not be converted
        """
        # If the virtual key code corresponds to a Key value, we prefer that
        if vk in self.escape:
            return self.escape[vk]

    def _process(self, wparam, lparam):
        msg = wparam
        vk = lparam

        # If the key has the UTF-16 flag, we treat it as a unicode character,
        # otherwise convert the event to a KeyCode; this may fail, and in that
        # case we pass None
        is_utf16 = msg & self._UTF16_FLAG
        if is_utf16:
            msg = msg ^ self._UTF16_FLAG
            scan = vk
            key = scan
        else:
            try:
                key = self._event_to_key(msg, vk)
            except OSError:
                key = None

        if msg in self._PRESS_MESSAGES:
            print(key)
            # self.on_press(key)

        elif msg in self._RELEASE_MESSAGES:
            pass


if __name__ == "__main__":
    o = WinKeyEvent()
    o.run()
