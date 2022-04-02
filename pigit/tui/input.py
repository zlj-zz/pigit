# -*- coding:utf-8 -*-
import os, sys
import tty, termios, select, fcntl
import signal
from subprocess import Popen, PIPE


# ===========
# Predefined
# ===========
ord2 = lambda x: x
B = lambda x: x.encode("iso8859-1")  # noqa: E731

# ==================
# Terminal encoding
# ==================
_byte_encoding = None


def set_byte_encoding(enc):
    assert enc in ("utf8", "narrow", "wide")
    global _byte_encoding
    _byte_encoding = enc


def get_byte_encoding():
    return _byte_encoding


def detect_encoding():
    # Try to determine if using a supported double-byte encoding
    import locale

    initial = locale.getlocale()
    try:
        try:
            locale.setlocale(locale.LC_ALL, "")
        except locale.Error:
            pass
        return locale.getlocale()[1] or ""
    except ValueError as e:
        # with invalid LANG value python will throw ValueError
        if e.args and e.args[0].startswith("unknown locale"):
            return ""
        else:
            raise
    finally:
        try:
            locale.setlocale(locale.LC_ALL, initial)
        except locale.Error:
            pass


if "detected_encoding" not in locals():
    detected_encoding = detect_encoding()
else:
    assert 0, "It worked!"

_target_encoding = None
_use_dec_special = True


def set_encoding(encoding):
    """
    Set the byte encoding to assume when processing strings and the
    encoding to use when converting unicode strings.
    """
    encoding = encoding.lower()

    global _target_encoding, _use_dec_special

    if encoding in ("utf-8", "utf8", "utf"):
        set_byte_encoding("utf8")

        _use_dec_special = False
    elif encoding in (
        "euc-jp",  # JISX 0208 only
        "euc-kr",
        "euc-cn",
        "euc-tw",  # CNS 11643 plain 1 only
        "gb2312",
        "gbk",
        "big5",
        "cn-gb",
        "uhc"
        # these shouldn't happen, should they?
        ,
        "eucjp",
        "euckr",
        "euccn",
        "euctw",
        "cncb",
    ):
        set_byte_encoding("wide")

        _use_dec_special = True
    else:
        set_byte_encoding("narrow")
        _use_dec_special = True

    # if encoding is valid for conversion from unicode, remember it
    _target_encoding = "ascii"
    try:
        if encoding:
            u"".encode(encoding)
            _target_encoding = encoding
    except LookupError:
        pass


# ==============
# Util function
# ==============
def within_double_byte(text, line_start, pos):
    """Return whether pos is within a double-byte encoded character.
    text -- byte string in question
    line_start -- offset of beginning of line (< pos)
    pos -- offset in question
    Return values:
    0 -- not within dbe char, or double_byte_encoding == False
    1 -- pos is on the 1st half of a dbe char
    2 -- pos is on the 2nd half of a dbe char
    """
    assert isinstance(text, bytes)
    v = ord2(text[pos])

    if v >= 0x40 and v < 0x7F:
        # might be second half of big5, uhc or gbk encoding
        if pos == line_start:
            return 0

        if ord2(text[pos - 1]) >= 0x81:
            if within_double_byte(text, line_start, pos - 1) == 1:
                return 2
        return 0

    if v < 0x80:
        return 0

    i = pos - 1
    while i >= line_start:
        if ord2(text[i]) < 0x80:
            break
        i -= 1

    if (pos - i) & 1:
        return 1
    return 2


def is_mouse_event(ev):
    return type(ev) == tuple and len(ev) == 4 and ev[0].find("mouse") >= 0


def is_mouse_press(ev):
    return ev.find("press") >= 0


# =================
## Input sequences
# =================
class MoreInputRequired(Exception):
    pass


def escape_modifier(digit):
    mode = ord(digit) - ord("1")
    return (
        "shift " * (mode & 1)
        + "meta " * ((mode & 2) // 2)
        + "ctrl " * ((mode & 4) // 4)
    )


# yapf: disable
input_sequences = [
    ('[A','up'),('[B','down'),('[C','right'),('[D','left'),
    ('[E','5'),('[F','end'),('[G','5'),('[H','home'),

    ('[1~','home'),('[2~','insert'),('[3~','delete'),('[4~','end'),
    ('[5~','page up'),('[6~','page down'),
    ('[7~','home'),('[8~','end'),

    ('[[A','f1'),('[[B','f2'),('[[C','f3'),('[[D','f4'),('[[E','f5'),

    ('[11~','f1'),('[12~','f2'),('[13~','f3'),('[14~','f4'),
    ('[15~','f5'),('[17~','f6'),('[18~','f7'),('[19~','f8'),
    ('[20~','f9'),('[21~','f10'),('[23~','f11'),('[24~','f12'),
    ('[25~','f13'),('[26~','f14'),('[28~','f15'),('[29~','f16'),
    ('[31~','f17'),('[32~','f18'),('[33~','f19'),('[34~','f20'),

    ('OA','up'),('OB','down'),('OC','right'),('OD','left'),
    ('OH','home'),('OF','end'),
    ('OP','f1'),('OQ','f2'),('OR','f3'),('OS','f4'),
    ('Oo','/'),('Oj','*'),('Om','-'),('Ok','+'),

    ('[Z','shift tab'),
    ('On', '.'),

    ('[200~', 'begin paste'), ('[201~', 'end paste'),
] + [
    (prefix + letter, modifier + key)
    for prefix, modifier in zip('O[', ('meta ', 'shift '))
    for letter, key in zip('abcd', ('up', 'down', 'right', 'left'))
] + [
    ("[" + digit + symbol, modifier + key)
    for modifier, symbol in zip(('shift ', 'meta '), '$^')
    for digit, key in zip('235678',
        ('insert', 'delete', 'page up', 'page down', 'home', 'end'))
] + [
    ('O' + chr(ord('p')+n), str(n)) for n in range(10)
] + [
    # modified cursor keys + home, end, 5 -- [#X and [1;#X forms
    (prefix+digit+letter, escape_modifier(digit) + key)
    for prefix in ("[", "[1;")
    for digit in "12345678"
    for letter,key in zip("ABCDEFGH",
        ('up','down','right','left','5','end','5','home'))
] + [
    # modified F1-F4 keys -- O#X form
    ("O"+digit+letter, escape_modifier(digit) + key)
    for digit in "12345678"
    for letter,key in zip("PQRS",('f1','f2','f3','f4'))
] + [
    # modified F1-F13 keys -- [XX;#~ form
    ("["+str(num)+";"+digit+"~", escape_modifier(digit) + key)
    for digit in "12345678"
    for num,key in zip(
        (3,5,6,11,12,13,14,15,17,18,19,20,21,23,24,25,26,28,29,31,32,33,34),
        ('delete', 'page up', 'page down',
        'f1','f2','f3','f4','f5','f6','f7','f8','f9','f10','f11',
        'f12','f13','f14','f15','f16','f17','f18','f19','f20'))
] + [
    # mouse reporting (special handling done in KeyqueueTrie)
    ('[M', 'mouse'),

    # mouse reporting for SGR 1006
    ('[<', 'sgrmouse'),

    # report status response
    ('[0n', 'status ok')
]
# yapf: enable

# This is added to button value to signal mouse release by curses_display
# and raw_display when we know which button was released.  NON-STANDARD
MOUSE_RELEASE_FLAG = 2048

# This 2-bit mask is used to check if the mouse release from curses or gpm
# is a double or triple release. 00 means single click, 01 double,
# 10 triple. NON-STANDARD
MOUSE_MULTIPLE_CLICK_MASK = 1536

# This is added to button value at mouse release to differentiate between
# single, double and triple press. Double release adds this times one,
# triple release adds this times two.  NON-STANDARD
MOUSE_MULTIPLE_CLICK_FLAG = 512

# xterm adds this to the button value to signal a mouse drag event
MOUSE_DRAG_FLAG = 32


class KeyqueueTrie(object):
    def __init__(self, sequences):
        self.data = {}
        for s, result in sequences:
            assert type(result) != dict
            self.add(self.data, s, result)

    def add(self, root, s, result):
        assert type(root) == dict, "trie conflict detected"
        assert len(s) > 0, "trie conflict detected"

        if ord(s[0]) in root:
            return self.add(root[ord(s[0])], s[1:], result)
        if len(s) > 1:
            d = {}
            root[ord(s[0])] = d
            return self.add(d, s[1:], result)
        root[ord(s)] = result

    def get(self, keys, more_available):

        result = self.get_recurse(self.data, keys, more_available)
        if not result:
            result = self.read_cursor_position(keys, more_available)
        return result

    def get_recurse(self, root, keys, more_available):
        if type(root) != dict:
            if root == "mouse":
                return self.read_mouse_info(keys, more_available)
            elif root == "sgrmouse":
                return self.read_sgrmouse_info(keys, more_available)
            return (root, keys)
        if not keys:
            # get more keys
            if more_available:
                raise MoreInputRequired()
            return None
        if keys[0] not in root:
            return None
        return self.get_recurse(root[keys[0]], keys[1:], more_available)

    def read_mouse_info(self, keys, more_available):
        if len(keys) < 3:
            if more_available:
                raise MoreInputRequired()
            return None

        b = keys[0] - 32
        x, y = (keys[1] - 33) % 256, (keys[2] - 33) % 256  # supports 0-255

        prefix = ""
        if b & 4:
            prefix = prefix + "shift "
        if b & 8:
            prefix = prefix + "meta "
        if b & 16:
            prefix = prefix + "ctrl "
        if (b & MOUSE_MULTIPLE_CLICK_MASK) >> 9 == 1:
            prefix = prefix + "double "
        if (b & MOUSE_MULTIPLE_CLICK_MASK) >> 9 == 2:
            prefix = prefix + "triple "

        # 0->1, 1->2, 2->3, 64->4, 65->5
        button = ((b & 64) // 64 * 3) + (b & 3) + 1

        if b & 3 == 3:
            action = "release"
            button = 0
        elif b & MOUSE_RELEASE_FLAG:
            action = "release"
        elif b & MOUSE_DRAG_FLAG:
            action = "drag"
        elif b & MOUSE_MULTIPLE_CLICK_MASK:
            action = "click"
        else:
            action = "press"

        return ((prefix + "mouse " + action, button, x, y), keys[3:])

    def read_sgrmouse_info(self, keys, more_available):
        # Helpful links:
        # https://stackoverflow.com/questions/5966903/how-to-get-mousemove-and-mouseclick-in-bash
        # http://invisible-island.net/xterm/ctlseqs/ctlseqs.pdf

        if not keys:
            if more_available:
                raise MoreInputRequired()
            return None

        value = ""
        pos_m = 0
        found_m = False
        for k in keys:
            value = value + chr(k)
            if (k is ord("M")) or (k is ord("m")):
                found_m = True
                break
            pos_m += 1
        if not found_m:
            if more_available:
                raise MoreInputRequired()
            return None

        (b, x, y) = value[:-1].split(";")

        # shift, meta, ctrl etc. is not communicated on my machine, so I
        # can't and won't be able to add support for it.
        # Double and triple clicks are not supported as well. They can be
        # implemented by using a timer. This timer can check if the last
        # registered click is below a certain threshold. This threshold
        # is normally set in the operating system itself, so setting one
        # here will cause an inconsistent behaviour. I do not plan to use
        # that feature, so I won't implement it.

        button = ((int(b) & 64) // 64 * 3) + (int(b) & 3) + 1
        x = int(x) - 1
        y = int(y) - 1

        if value[-1] == "M":
            if int(b) & MOUSE_DRAG_FLAG:
                action = "drag"
            else:
                action = "press"
        else:
            action = "release"

        return (("mouse " + action, button, x, y), keys[pos_m + 1 :])

    def read_cursor_position(self, keys, more_available):
        """
        Interpret cursor position information being sent by the
        user's terminal.  Returned as ('cursor position', x, y)
        where (x, y) == (0, 0) is the top left of the screen.
        """
        if not keys:
            if more_available:
                raise MoreInputRequired()
            return None
        if keys[0] != ord("["):
            return None
        # read y value
        y = 0
        i = 1
        for k in keys[i:]:
            i += 1
            if k == ord(";"):
                if not y:
                    return None
                else:
                    break
            if k < ord("0") or k > ord("9"):
                return None
            if not y and k == ord("0"):
                return None
            y = y * 10 + k - ord("0")
        if not keys[i:]:
            if more_available:
                raise MoreInputRequired()
            return None
        # read x value
        x = 0
        for k in keys[i:]:
            i += 1
            if k == ord("R"):
                return None if not x else (("cursor position", x - 1, y - 1), keys[i:])
            if k < ord("0") or k > ord("9"):
                return None
            if not x and k == ord("0"):
                return None
            x = x * 10 + k - ord("0")
        if not keys[i:] and more_available:
            raise MoreInputRequired()
        return None


# ===============================================
# Build the input trie from input_sequences list
input_trie = KeyqueueTrie(input_sequences)
# ===============================================

ESC = "\x1b"
MOUSE_TRACKING_ON = ESC + "[?1000h" + ESC + "[?1002h" + ESC + "[?1006h"
MOUSE_TRACKING_OFF = ESC + "[?1006l" + ESC + "[?1002l" + ESC + "[?1000l"

_keyconv = {
    -1: None,
    8: "backspace",
    9: "tab",
    10: "enter",
    13: "enter",
    127: "backspace",
    # curses-only keycodes follow..  (XXX: are these used anymore?)
    258: "down",
    259: "up",
    260: "left",
    261: "right",
    262: "home",
    263: "backspace",
    265: "f1",
    266: "f2",
    267: "f3",
    268: "f4",
    269: "f5",
    270: "f6",
    271: "f7",
    272: "f8",
    273: "f9",
    274: "f10",
    275: "f11",
    276: "f12",
    277: "shift f1",
    278: "shift f2",
    279: "shift f3",
    280: "shift f4",
    281: "shift f5",
    282: "shift f6",
    283: "shift f7",
    284: "shift f8",
    285: "shift f9",
    286: "shift f10",
    287: "shift f11",
    288: "shift f12",
    330: "delete",
    331: "insert",
    338: "page down",
    339: "page up",
    343: "enter",  # on numpad
    350: "5",  # on numpad
    360: "end",
}


def process_keyqueue(codes, more_available):
    """
    codes -- list of key codes
    more_available -- if True then raise MoreInputRequired when in the
        middle of a character sequence (escape/utf8/wide) and caller
        will attempt to send more key codes on the next call.
    returns (list of input, list of remaining key codes).
    """
    code = codes[0]
    if code >= 32 and code <= 126:
        key = chr(code)
        return [key], codes[1:]
    if code in _keyconv:
        return [_keyconv[code]], codes[1:]
    if code > 0 and code < 27:
        return ["ctrl %s" % chr(ord("a") + code - 1)], codes[1:]
    if code > 27 and code < 32:
        return ["ctrl %s" % chr(ord("A") + code - 1)], codes[1:]

    em = get_byte_encoding()

    if em == "wide" and code < 256 and within_double_byte(chr(code), 0, 0):
        if not codes[1:]:
            if more_available:
                raise MoreInputRequired()
        if codes[1:] and codes[1] < 256:
            db = chr(code) + chr(codes[1])
            if within_double_byte(db, 0, 1):
                return [db], codes[2:]
    if em == "utf8" and code > 127 and code < 256:
        if code & 0xE0 == 0xC0:  # 2-byte form
            need_more = 1
        elif code & 0xF0 == 0xE0:  # 3-byte form
            need_more = 2
        elif code & 0xF8 == 0xF0:  # 4-byte form
            need_more = 3
        else:
            return ["<%d>" % code], codes[1:]

        for i in range(need_more):
            if len(codes) - 1 <= i:
                if more_available:
                    raise MoreInputRequired()
                else:
                    return ["<%d>" % code], codes[1:]
            k = codes[i + 1]
            if k > 256 or k & 0xC0 != 0x80:
                return ["<%d>" % code], codes[1:]

        s = bytes(codes[: need_more + 1])

        assert isinstance(s, bytes)
        try:
            return [s.decode("utf-8")], codes[need_more + 1 :]
        except UnicodeDecodeError:
            return ["<%d>" % code], codes[1:]

    if code > 127 and code < 256:
        key = chr(code)
        return [key], codes[1:]
    if code != 27:
        return ["<%d>" % code], codes[1:]

    result = input_trie.get(codes[1:], more_available)

    if result is not None:
        result, remaining_codes = result
        return [result], remaining_codes

    if codes[1:]:
        # Meta keys -- ESC+Key form
        run, remaining_codes = process_keyqueue(codes[1:], more_available)
        if is_mouse_event(run[0]):
            return ["esc"] + run, remaining_codes
        if run[0] == "esc" or run[0].find("meta ") >= 0:
            return ["esc"] + run, remaining_codes
        return ["meta " + run[0]] + run[1:], remaining_codes

    return ["esc"], codes[1:]


class InputTerminal(object):
    def __init__(self):
        super(InputTerminal, self).__init__()
        self._signal_keys_set = False
        self._old_signal_keys = None

    def tty_signal_keys(
        self, intr=None, quit=None, start=None, stop=None, susp=None, fileno=None
    ):
        """
        Read and/or set the tty's signal character settings.
        This function returns the current settings as a tuple.
        Use the string 'undefined' to unmap keys from their signals.
        The value None is used when no change is being made.
        Setting signal keys is done using the integer ascii
        code for the key, eg.  3 for CTRL+C.
        If this function is called after start() has been called
        then the original settings will be restored when stop()
        is called.
        """
        if fileno is None:
            fileno = sys.stdin.fileno()
        if not os.isatty(fileno):
            return

        tattr = termios.tcgetattr(fileno)
        sattr = tattr[6]
        skeys = (
            sattr[termios.VINTR],
            sattr[termios.VQUIT],
            sattr[termios.VSTART],
            sattr[termios.VSTOP],
            sattr[termios.VSUSP],
        )

        if intr == "undefined":
            intr = 0
        if quit == "undefined":
            quit = 0
        if start == "undefined":
            start = 0
        if stop == "undefined":
            stop = 0
        if susp == "undefined":
            susp = 0

        if intr is not None:
            tattr[6][termios.VINTR] = intr
        if quit is not None:
            tattr[6][termios.VQUIT] = quit
        if start is not None:
            tattr[6][termios.VSTART] = start
        if stop is not None:
            tattr[6][termios.VSTOP] = stop
        if susp is not None:
            tattr[6][termios.VSUSP] = susp

        if (
            intr is not None
            or quit is not None
            or start is not None
            or stop is not None
            or susp is not None
        ):
            termios.tcsetattr(fileno, termios.TCSADRAIN, tattr)
            self._signal_keys_set = True

        return skeys


class PosixInput(InputTerminal):
    def __init__(self, input=sys.stdin, output=sys.stdout) -> None:
        super().__init__()

        self._keyqueue = []
        self.prev_input_resize = 0
        self._partial_codes = None
        self._input_timeout = None
        self.set_input_timeouts()
        self._next_timeout = None
        self._resized = False

        self.gpm_mev = None
        self.gpm_event_pending = False
        self._mouse_tracking_enabled = False
        self.signal_handler_setter = signal.signal

        # Our connections to the world
        self._term_output_file = output
        self._term_input_file = input

        # pipe for signalling external event loops about resize events
        self._resize_pipe_rd, self._resize_pipe_wr = os.pipe()
        fcntl.fcntl(self._resize_pipe_rd, fcntl.F_SETFL, os.O_NONBLOCK)

    def _input_fileno(self):
        """
        Returns the fileno of the input stream, or None if it doesn't have one.
        A stream without a fileno can't participate in whatever.
        """
        if hasattr(self._term_input_file, "fileno"):
            return self._term_input_file.fileno()
        else:
            return None

    def set_input_timeouts(self, max_wait=None, complete_wait=0.125, resize_wait=0.125):
        """
        Set the get_input timeout values.  All values are in floating
        point numbers of seconds.
        max_wait -- amount of time in seconds to wait for input when
            there is no input pending, wait forever if None
        complete_wait -- amount of time in seconds to wait when
            get_input detects an incomplete escape sequence at the
            end of the available input
        resize_wait -- amount of time in seconds to wait for more input
            after receiving two screen resize requests in a row to
            stop Urwid from consuming 100% cpu during a gradual
            window resize operation
        """
        self.max_wait = max_wait
        if max_wait is not None:
            if self._next_timeout is None:
                self._next_timeout = max_wait
            else:
                self._next_timeout = min(self._next_timeout, self.max_wait)
        self.complete_wait = complete_wait
        self.resize_wait = resize_wait

    def _sigwinch_handler(self, signum, frame=None):
        """
        frame -- will always be None when the GLib event loop is being used.
        """

        if not self._resized:
            os.write(self._resize_pipe_wr, B("R"))
        self._resized = True

    def signal_init(self):
        """
        Called in the startup of run wrapper to set the SIGWINCH
        signal handlers.
        Override this function to call from main thread in threaded
        applications.
        """
        self.signal_handler_setter(signal.SIGWINCH, self._sigwinch_handler)

    def signal_restore(self):
        """
        Called in the finally block of run wrapper to restore the
        SIGWINCH signal handlers.
        Override this function to call from main thread in threaded
        applications.
        """
        self.signal_handler_setter(signal.SIGCONT, signal.SIG_DFL)

    def set_mouse_tracking(self, enable=True):
        """
        Enable (or disable) mouse tracking.
        After calling this function get_input will include mouse
        click events along with keystrokes.
        """
        enable = bool(enable)
        if enable == self._mouse_tracking_enabled:
            return

        self._mouse_tracking(enable)
        self._mouse_tracking_enabled = enable

    def _mouse_tracking(self, enable):
        if enable:
            self.write(MOUSE_TRACKING_ON)
            self._start_gpm_tracking()
        else:
            self.write(MOUSE_TRACKING_OFF)
            self._stop_gpm_tracking()

    def _start_gpm_tracking(self):
        if not os.path.isfile("/usr/bin/mev"):
            return
        if not os.environ.get("TERM", "").lower().startswith("linux"):
            return
        if not Popen:
            return
        m = Popen(
            ["/usr/bin/mev", "-e", "158"], stdin=PIPE, stdout=PIPE, close_fds=True
        )
        fcntl.fcntl(m.stdout.fileno(), fcntl.F_SETFL, os.O_NONBLOCK)
        self.gpm_mev = m

    def _stop_gpm_tracking(self):
        if not self.gpm_mev:
            return
        os.kill(self.gpm_mev.pid, signal.SIGINT)
        os.waitpid(self.gpm_mev.pid, 0)
        self.gpm_mev = None

    def start(self):
        fd = self._input_fileno()
        if fd is not None and os.isatty(fd):
            self._old_termios_settings = termios.tcgetattr(fd)
            tty.setcbreak(fd)

        self.signal_init()
        self._next_timeout = self.max_wait

        if not self._signal_keys_set:
            self._old_signal_keys = self.tty_signal_keys(fileno=fd)

        # restore mouse tracking to previous state
        self._mouse_tracking(self._mouse_tracking_enabled)

    def stop(self):
        self.signal_restore()

        fd = self._input_fileno()
        if fd is not None and os.isatty(fd):
            termios.tcsetattr(fd, termios.TCSADRAIN, self._old_termios_settings)

        self._mouse_tracking(False)

    def _wait_for_input_ready(self, timeout):
        ready = None
        fd_list = []
        fd = self._input_fileno()
        if fd is not None:
            fd_list.append(fd)
        while True:
            try:
                if timeout is None:
                    ready, w, err = select.select(fd_list, [], fd_list)
                else:
                    ready, w, err = select.select(fd_list, [], fd_list, timeout)
                break
            except select.error as e:
                if e.args[0] != 4:
                    raise
                if self._resized:
                    ready = []
                    break
        return ready

    def _getch(self, timeout):
        ready = self._wait_for_input_ready(timeout)
        fd = self._input_fileno()
        if fd is not None and fd in ready:
            return ord(os.read(fd, 1))
        return -1

    def _getch_nodelay(self):
        return self._getch(0)

    def _get_keyboard_codes(self):
        codes = []
        while True:
            code = self._getch_nodelay()
            if code < 0:
                break
            codes.append(code)
        return codes

    def _encode_gpm_event(self):
        self.gpm_event_pending = False
        s = self.gpm_mev.stdout.readline().decode("ascii")
        l = s.split(",")
        if len(l) != 6:
            # unexpected output, stop tracking
            self._stop_gpm_tracking()
            return []
        ev, x, y, ign, b, m = s.split(",")
        ev = int(ev.split("x")[-1], 16)
        x = int(x.split(" ")[-1])
        y = int(y.lstrip().split(" ")[0])
        b = int(b.split(" ")[-1])
        m = int(m.split("x")[-1].rstrip(), 16)

        # convert to xterm-like escape sequence

        last = next = self.last_bstate
        l = []

        mod = 0
        if m & 1:
            mod |= 4  # shift
        if m & 10:
            mod |= 8  # alt
        if m & 4:
            mod |= 16  # ctrl

        def append_button(b):
            b |= mod
            l.extend([27, ord("["), ord("M"), b + 32, x + 32, y + 32])

        if ev == 20 or ev == 36 or ev == 52:  # press
            if b & 4 and last & 1 == 0:
                append_button(0)
                next |= 1
            if b & 2 and last & 2 == 0:
                append_button(1)
                next |= 2
            if b & 1 and last & 4 == 0:
                append_button(2)
                next |= 4
        elif ev == 146:  # drag
            if b & 4:
                append_button(0 + MOUSE_DRAG_FLAG)
            elif b & 2:
                append_button(1 + MOUSE_DRAG_FLAG)
            elif b & 1:
                append_button(2 + MOUSE_DRAG_FLAG)
        else:  # release
            if b & 4 and last & 1:
                append_button(0 + MOUSE_RELEASE_FLAG)
                next &= ~1
            if b & 2 and last & 2:
                append_button(1 + MOUSE_RELEASE_FLAG)
                next &= ~2
            if b & 1 and last & 4:
                append_button(2 + MOUSE_RELEASE_FLAG)
                next &= ~4
        if ev == 40:  # double click (release)
            if b & 4 and last & 1:
                append_button(0 + MOUSE_MULTIPLE_CLICK_FLAG)
            if b & 2 and last & 2:
                append_button(1 + MOUSE_MULTIPLE_CLICK_FLAG)
            if b & 1 and last & 4:
                append_button(2 + MOUSE_MULTIPLE_CLICK_FLAG)
        elif ev == 52:
            if b & 4 and last & 1:
                append_button(0 + MOUSE_MULTIPLE_CLICK_FLAG * 2)
            if b & 2 and last & 2:
                append_button(1 + MOUSE_MULTIPLE_CLICK_FLAG * 2)
            if b & 1 and last & 4:
                append_button(2 + MOUSE_MULTIPLE_CLICK_FLAG * 2)

        self.last_bstate = next
        return l

    def _get_gpm_codes(self):
        codes = []
        try:
            while self.gpm_mev is not None and self.gpm_event_pending:
                codes.extend(self._encode_gpm_event())
        except IOError as e:
            if e.args[0] != 11:
                raise
        return codes

    def get_available_raw_input(self):
        """
        Return any currently-available input.  Does not block.
        This method is only used by the default `hook_event_loop`
        implementation; you can safely ignore it if you implement your own.
        """
        codes = self._get_gpm_codes() + self._get_keyboard_codes()

        if self._partial_codes:
            codes = self._partial_codes + codes
            self._partial_codes = None

        # clean out the pipe used to signal external event loops
        # that a resize has occurred
        try:
            while True:
                os.read(self._resize_pipe_rd, 1)
        except OSError:
            pass

        return codes

    def parse_input(self, event_loop, callback, codes, wait_for_more=True):
        """
        Read any available input from get_available_raw_input, parses it into
        keys, and calls the given callback.
        The current implementation tries to avoid any assumptions about what
        the screen or event loop look like; it only deals with parsing keycodes
        and setting a timeout when an incomplete one is detected.
        `codes` should be a sequence of keycodes, i.e. bytes.  A bytearray is
        appropriate, but beware of using bytes, which only iterates as integers
        on Python 3.
        """
        # Note: event_loop may be None for 100% synchronous support, only used
        # by get_input.  Not documented because you shouldn't be doing it.
        if self._input_timeout and event_loop:
            event_loop.remove_alarm(self._input_timeout)
            self._input_timeout = None

        original_codes = codes
        processed = []
        try:
            while codes:
                run, codes = process_keyqueue(codes, wait_for_more)
                processed.extend(run)
        except MoreInputRequired:
            # Set a timer to wait for the rest of the input; if it goes off
            # without any new input having come in, use the partial input
            k = len(original_codes) - len(codes)
            processed_codes = original_codes[:k]
            self._partial_codes = codes

            def _parse_incomplete_input():
                self._input_timeout = None
                self._partial_codes = None
                self.parse_input(event_loop, callback, codes, wait_for_more=False)

            if event_loop:
                self._input_timeout = event_loop.alarm(
                    self.complete_wait, _parse_incomplete_input
                )
            else:
                # When there is no `eventloop`, and turn on `wait more`.
                run, codes = self.parse_input(
                    event_loop, callback, codes, wait_for_more=False
                )
                processed.extend(run)
                processed_codes = original_codes

        else:
            processed_codes = original_codes
            self._partial_codes = None

        if self._resized:
            processed.append("window resize")
            self._resized = False

        if callback:
            callback(processed, processed_codes)
        else:
            # For get_input
            return processed, processed_codes

    def get_input(self, raw_keys=False):
        """Return pending input as a list.
        raw_keys -- return raw keycodes as well as translated versions
        This function will immediately return all the input since the
        last time it was called.  If there is no input pending it will
        wait before returning an empty list.  The wait time may be
        configured with the set_input_timeouts function.
        If raw_keys is False (default) this function will return a list
        of keys pressed.  If raw_keys is True this function will return
        a ( keys pressed, raw keycodes ) tuple instead.
        Examples of keys returned:
        * ASCII printable characters:  " ", "a", "0", "A", "-", "/"
        * ASCII control characters:  "tab", "enter"
        * Escape sequences:  "up", "page up", "home", "insert", "f1"
        * Key combinations:  "shift f1", "meta a", "ctrl b"
        * Window events:  "window resize"
        When a narrow encoding is not enabled:
        * "Extended ASCII" characters:  "\\xa1", "\\xb2", "\\xfe"
        When a wide encoding is enabled:
        * Double-byte characters:  "\\xa1\\xea", "\\xb2\\xd4"
        When utf8 encoding is enabled:
        * Unicode characters: u"\\u00a5", u'\\u253c"
        Examples of mouse events returned:
        * Mouse button press: ('mouse press', 1, 15, 13),
                              ('meta mouse press', 2, 17, 23)
        * Mouse drag: ('mouse drag', 1, 16, 13),
                      ('mouse drag', 1, 17, 13),
                      ('ctrl mouse drag', 1, 18, 13)
        * Mouse button release: ('mouse release', 0, 18, 13),
                                ('ctrl mouse release', 0, 17, 23)
        """

        self._wait_for_input_ready(self._next_timeout)
        keys, raw = self.parse_input(None, None, self.get_available_raw_input())

        # Avoid pegging CPU at 100% when slowly resizing
        if keys == ["window resize"] and self.prev_input_resize:
            while True:
                self._wait_for_input_ready(self.resize_wait)
                keys, raw2 = self.parse_input(
                    None, None, self.get_available_raw_input()
                )
                raw += raw2
                # if not keys:
                #    keys, raw2 = self._get_input(
                #        self.resize_wait)
                #    raw += raw2
                if keys != ["window resize"]:
                    break
            if keys[-1:] != ["window resize"]:
                keys.append("window resize")

        if keys == ["window resize"]:
            self.prev_input_resize = 2
        elif self.prev_input_resize == 2 and not keys:
            self.prev_input_resize = 1
        else:
            self.prev_input_resize = 0

        if raw_keys:
            return keys, raw
        return keys

    def write(self, data):
        """Write some data to the terminal.
        You may wish to override this if you're using something other than
        regular files for input and output.
        """
        self._term_output_file.write(data)

    def flush(self):
        """Flush the output buffer.
        You may wish to override this if you're using something other than
        regular files for input and output.
        """
        self._term_output_file.flush()


if __name__ == "__main__":
    handle = PosixInput()
    # handle.set_input_timeouts(0.125)
    handle.start()
    handle.set_mouse_tracking()
    handle.set_input_timeouts(0.125)
    while True:
        res = handle.get_input(raw_keys=True)
        print(res)
