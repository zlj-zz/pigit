"""
Module: tests/termui/test_session.py
Description: Tests for terminal session state management.
Author: Zev
Date: 2026-05-20
"""

from __future__ import annotations

from io import StringIO
from unittest import mock

import pytest

from pigit.termui._session import Session


class FakeTTY(StringIO):
    def isatty(self):
        return True

    def fileno(self):
        return 0

    def flush(self):
        pass


class FakeNonTTY(StringIO):
    def isatty(self):
        return False

    def fileno(self):
        return 0

    def flush(self):
        pass


class TestSessionEnterExit:
    def test_enter_raises_without_tty(self):
        stdin = FakeNonTTY()
        stdout = FakeNonTTY()
        session = Session(stdin=stdin, stdout=stdout)
        with pytest.raises(RuntimeError):
            session.__enter__()

    def test_enter_sets_cbreak_and_hides_cursor(self):
        stdin = FakeTTY()
        stdout = FakeTTY()
        session = Session(stdin=stdin, stdout=stdout)

        with mock.patch("sys.platform", "linux"):
            fake_termios = mock.Mock()
            fake_tty = mock.Mock()
            with mock.patch.dict(
                "sys.modules", {"termios": fake_termios, "tty": fake_tty}
            ):
                result = session.__enter__()
                assert result is session
                fake_tty.setcbreak.assert_called_once()
                fake_termios.tcgetattr.assert_called_once()

    def test_enter_with_alt_screen(self):
        stdin = FakeTTY()
        stdout = FakeTTY()
        session = Session(alt_screen=True, stdin=stdin, stdout=stdout)

        with mock.patch("sys.platform", "linux"):
            fake_termios = mock.Mock()
            fake_tty = mock.Mock()
            with mock.patch.dict(
                "sys.modules", {"termios": fake_termios, "tty": fake_tty}
            ):
                session.__enter__()
                assert "\033[?1049h" in stdout.getvalue()

    def test_exit_restores_termios(self):
        stdin = FakeTTY()
        stdout = FakeTTY()
        session = Session(stdin=stdin, stdout=stdout)
        session._old_termios = ["mock_attrs"]

        with mock.patch("sys.platform", "linux"):
            fake_termios = mock.Mock()
            with mock.patch.dict("sys.modules", {"termios": fake_termios}):
                session.__exit__(None, None, None)
                fake_termios.tcsetattr.assert_called_once()

    def test_exit_on_windows_skips_termios(self):
        stdin = FakeTTY()
        stdout = FakeTTY()
        session = Session(stdin=stdin, stdout=stdout)

        with mock.patch("sys.platform", "win32"):
            session.__exit__(None, None, None)
            # Should not raise even without termios module


class TestSessionSuspendResume:
    def test_suspend_restores_cursor(self):
        stdin = FakeTTY()
        stdout = FakeTTY()
        session = Session(alt_screen=True, stdin=stdin, stdout=stdout)
        session._suspended = False

        with mock.patch("sys.platform", "linux"):
            fake_termios = mock.Mock()
            with mock.patch.dict("sys.modules", {"termios": fake_termios}):
                session.suspend()
                assert session._suspended is True
                # Idempotent second call
                session.suspend()
                assert session._suspended is True

    def test_suspend_restores_termios(self):
        stdin = FakeTTY()
        stdout = FakeTTY()
        session = Session(alt_screen=False, stdin=stdin, stdout=stdout)
        session._old_termios = ["mock_attrs"]
        session._suspended = False

        with mock.patch("sys.platform", "linux"):
            fake_termios = mock.Mock()
            with mock.patch.dict("sys.modules", {"termios": fake_termios}):
                session.suspend()
                fake_termios.tcsetattr.assert_called_once()

    def test_resume_sets_cbreak(self):
        stdin = FakeTTY()
        stdout = FakeTTY()
        session = Session(alt_screen=True, stdin=stdin, stdout=stdout)
        session._suspended = True

        with mock.patch("sys.platform", "linux"):
            fake_tty = mock.Mock()
            with mock.patch.dict("sys.modules", {"tty": fake_tty}):
                session.resume()
                assert session._suspended is False
                fake_tty.setcbreak.assert_called_once()
                # Idempotent second call
                session.resume()
                assert session._suspended is False

    def test_resume_no_alt_screen(self):
        stdin = FakeTTY()
        stdout = FakeTTY()
        session = Session(alt_screen=False, stdin=stdin, stdout=stdout)
        session._suspended = True

        with mock.patch("sys.platform", "linux"):
            fake_tty = mock.Mock()
            with mock.patch.dict("sys.modules", {"tty": fake_tty}):
                session.resume()
                assert "\033[?1049h" not in stdout.getvalue()
                assert "\033[?25l" in stdout.getvalue()

    def test_resume_no_op_when_not_suspended(self):
        stdin = FakeTTY()
        stdout = FakeTTY()
        session = Session(stdin=stdin, stdout=stdout)
        session._suspended = False

        with mock.patch("sys.platform", "linux"):
            fake_tty = mock.Mock()
            with mock.patch.dict("sys.modules", {"tty": fake_tty}):
                session.resume()
                fake_tty.setcbreak.assert_not_called()

    def test_suspend_no_alt_screen(self):
        stdin = FakeTTY()
        stdout = FakeTTY()
        session = Session(alt_screen=False, stdin=stdin, stdout=stdout)
        session._suspended = False

        with mock.patch("sys.platform", "linux"):
            fake_termios = mock.Mock()
            with mock.patch.dict("sys.modules", {"termios": fake_termios}):
                session.suspend()
                # Should not write alt screen escape
                assert session._suspended is True

    def test_context_manager_restores_on_exception(self):
        stdin = FakeTTY()
        stdout = FakeTTY()
        session = Session(stdin=stdin, stdout=stdout)
        session._old_termios = ["mock_attrs"]

        with mock.patch("sys.platform", "linux"):
            fake_termios = mock.Mock()
            fake_tty = mock.Mock()
            with mock.patch.dict(
                "sys.modules", {"termios": fake_termios, "tty": fake_tty}
            ):
                try:
                    with session:
                        raise ValueError("boom")
                except ValueError:
                    pass
                fake_termios.tcsetattr.assert_called_once()

    def test_enter_on_windows_skips_termios(self):
        stdin = FakeTTY()
        stdout = FakeTTY()
        session = Session(stdin=stdin, stdout=stdout)

        with mock.patch("sys.platform", "win32"):
            result = session.__enter__()
            assert result is session
            # Should not raise even without termios/tty module

    def test_resume_on_windows_skips_termios(self):
        stdin = FakeTTY()
        stdout = FakeTTY()
        session = Session(alt_screen=True, stdin=stdin, stdout=stdout)
        session._suspended = True

        with mock.patch("sys.platform", "win32"):
            session.resume()
            assert session._suspended is False

    def test_exit_with_alt_screen(self):
        stdin = FakeTTY()
        stdout = FakeTTY()
        session = Session(alt_screen=True, stdin=stdin, stdout=stdout)
        session._old_termios = ["mock_attrs"]

        with mock.patch("sys.platform", "linux"):
            fake_termios = mock.Mock()
            with mock.patch.dict("sys.modules", {"termios": fake_termios}):
                session.__exit__(None, None, None)
                fake_termios.tcsetattr.assert_called_once()
