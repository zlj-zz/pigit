# -*- coding: utf-8 -*-
"""Coverage for :mod:`pigit.ext.log` and :mod:`pigit.ext.executor` edge paths."""

import logging
from unittest.mock import MagicMock, patch

import pytest

from pigit.ext.executor import (
    Executor,
    REDIRECT,
    REPLY,
    DECODE,
    WAITING,
    _split_cmd_argv,
)
from pigit.ext import log as log_mod


@pytest.fixture(autouse=True)
def _strip_pigit_log_handlers():
    yield
    root = logging.getLogger()
    for h in list(root.handlers):
        if getattr(h, "_pigit_log_handler", False):
            root.removeHandler(h)
            h.close()


def test_setup_logging_debug_and_repeat(tmp_path):
    log_file = tmp_path / "d.log"
    log_mod.setup_logging(debug=True, log_file=str(log_file))
    log_mod.setup_logging(debug=False, log_file=None)
    logging.getLogger("t").warning("hello")
    assert log_file.is_file()


def test_logger_named_cache():
    a = log_mod.logger("same")
    b = log_mod.logger("same")
    assert a is b


def test_install_uncaught_twice_no_double_wrap():
    log_mod._UNCAUGHT_HOOKS_INSTALLED = False
    log_mod.install_uncaught_exception_logging()
    import sys

    hook1 = sys.excepthook
    log_mod.install_uncaught_exception_logging()
    hook2 = sys.excepthook
    assert hook1 is hook2


def test_split_cmd_argv_shlex_valueerror_fallback():
    with patch("pigit.ext.executor.shlex.split", side_effect=ValueError):
        assert _split_cmd_argv("git status -s") == ["git", "status", "-s"]


@pytest.mark.asyncio
async def test_run_async_subprocess_empty_argv():
    ex = Executor()
    es = ex.generate_popen_state(REPLY | REDIRECT | DECODE | WAITING, {})
    r = await ex.run_async_subprocess(es, "", {"shell": False, "stdout": -1, "stderr": -1})
    assert r[0] == 1


def test_exec_popen_failure_logged():
    log = MagicMock()
    ex = Executor(log=log)
    with patch("pigit.ext.executor.Popen", side_effect=OSError("fail")):
        r = ex.exec("true", flags=REPLY | REDIRECT | DECODE | WAITING)
    assert r == (None, None, None)
    log.warning.assert_called()


def test_exec_stream_nonzero_and_stderr():
    log = MagicMock()
    ex = Executor(log=log)

    class _Proc:
        returncode = 2

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        stdout = iter([b"line\n"])
        stderr = MagicMock()
        stderr.read.return_value = b"err"

    with patch("pigit.ext.executor.Popen", return_value=_Proc()):
        lines = list(ex.exec_stream("x"))
    assert lines == ["line"]
    assert log.warning.called


def test_exec_stream_stdout_none_early_exit():
    log = MagicMock()
    ex = Executor(log=log)

    class _Proc:
        returncode = 0
        stdout = None

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    with patch("pigit.ext.executor.Popen", return_value=_Proc()):
        assert list(ex.exec_stream("x")) == []


def test_detect_encoding_fallback():
    from pigit.ext.executor import _detect_encoding

    raw = b"\xff\xfe"
    enc = _detect_encoding(raw)
    assert enc == "" or isinstance(enc, str)
