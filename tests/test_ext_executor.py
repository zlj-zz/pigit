import sys
import time
import textwrap
import pytest
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from pigit.ext.executor import (
    DECODE,
    REDIRECT,
    REPLY,
    SILENT,
    WAIT_ENTER,
    WAITING,
    Executor,
)

win_skip_mark = pytest.mark.skipif(sys.platform == "win32", reason="windows skip.")


class TestExecutor:
    @classmethod
    def setup_class(cls):
        cls.executor = Executor(print)

    @pytest.mark.parametrize(
        "cmd, flags, kws, expected",
        [
            # Test case 1: Happy path, command as string, no flags
            ("ls -l", 0, {}, (None, None, None)),
            # Test case 2: Happy path, command as list, no flags
            (["ls", "-l"], 0, {}, (None, None, None)),
            # Test case 3: Happy path, command as tuple, no flags
            (("ls", "-l"), 0, {}, (None, None, None)),
            # Test case 4: Happy path, command as string, with flags
            # ("ls -l", REPLY, {}, (0, None, "output")),
            # Test case 5: Error case, command as string, with flags, command fails
            # ("ls -l", DECODE | REPLY | REDIRECT | WAITING, {}, (1, "error", None)),
        ],
        ids=[
            "command-string-no-flags",
            "command-list-no-flags",
            "command-tuple-no-flags",
            # "command-string-with-flags",
            # "command-string-with-flags-command-fails",
        ],
    )
    def test_exec(self, cmd, flags, kws, expected):
        # Arrange
        executor = Executor(print)

        with patch("pigit.ext.executor.Popen") as mock_popen:
            mock_proc = mock_popen.return_value
            # FIXME: can not right mock.
            mock_proc.returncode = expected[0]
            mock_proc.communicate.return_value = (expected[2] or "", expected[1] or "")

            # Act
            result = executor.exec(cmd, flags=flags, **kws)

            # Assert
            assert result == expected
            # mock_popen.assert_called_once_with(args=cmd, **kws)

    def test_exec_stream_yields_decoded_lines(self):
        with patch("pigit.ext.executor.Popen") as mock_popen:
            mock_proc = MagicMock()
            mock_popen.return_value = mock_proc
            mock_proc.__enter__.return_value = mock_proc
            mock_proc.__exit__.return_value = None
            mock_proc.stdout = iter([b"one\n", b"two\n"])
            mock_proc.stderr.read.return_value = b""
            mock_proc.returncode = 0

            executor = Executor()
            lines = list(executor.exec_stream("git log", cwd="/tmp"))

        assert lines == ["one", "two"]

    @win_skip_mark
    def test_exec_with_more(self):
        print()

        print(self.executor.exec("pwd", flags=WAITING | REDIRECT))

        print(self.executor.exec("pwd", flags=REPLY))
        print(self.executor.exec("pwd", flags=REPLY | DECODE))
        # # print(self.executor.exec("pwd", flags=REPLY | ENCODING | WAIT_ENTER))

        print(self.executor.exec("xxxxxxxx", flags=REPLY))

        assert self.executor.exec(["ls"], shell=True) == (None, None, None)
        assert self.executor.exec("ls", flags=REPLY | SILENT) == (0, None, None)
        assert self.executor.exec(["which", "python3"], flags=SILENT, shell=True) == (
            None,
            None,
            None,
        )

    @pytest.mark.asyncio
    async def test_exec_async(self, monkeypatch):
        # String command defaults to shell=True → create_subprocess_shell (aligned with sync exec).
        mock_shell = AsyncMock()
        mock_shell.return_value.communicate.return_value = (
            b"output",
            b"error",
        )
        mock_shell.return_value.returncode = 0
        monkeypatch.setattr("asyncio.create_subprocess_shell", mock_shell)

        executor = Executor()

        result = await executor.exec_async(
            "ls -l", flags=DECODE | REPLY | REDIRECT | WAITING
        )

        assert result == [(0, "error", "output")]
        mock_shell.assert_called_once_with(
            "ls -l", start_new_session=True, stdout=-1, stderr=-1
        )

    @pytest.mark.asyncio
    async def test_exec_async_string_shell_false_uses_shlex_exec(self, monkeypatch):
        mock_exec = AsyncMock()
        mock_exec.return_value.communicate.return_value = (b"x", b"")
        mock_exec.return_value.returncode = 0
        monkeypatch.setattr("asyncio.create_subprocess_exec", mock_exec)

        executor = Executor()
        await executor.exec_async(
            'echo "hello world"',
            flags=DECODE | REPLY | REDIRECT | WAITING,
            shell=False,
        )

        mock_exec.assert_called_once()
        assert mock_exec.call_args[0][:2] == ("echo", "hello world")

    def test_exec_parallel(self):
        code = textwrap.dedent(
            """\
            # -*- coding:utf-8 -*-

            if __name__ == '__main__':
                import time

                print({0}, end='')
                time.sleep(int({0}))
                print({0}, end='')
            """
        )

        cmd = (
            "python"
            if self.executor.exec("python -V", flags=REPLY)[0] == 0
            else "python3"
        )

        cmds = [[cmd, "-c", code.format(i)] for i in range(3, 0, -1)]
        # pprint(cmds)

        start_t = time.time()
        results = self.executor.exec_parallel(*cmds, flags=WAITING | REDIRECT | DECODE)
        assert results == [(None, None, None)] * 3
        # results = self.executor.exec_async(*cmds, flags=REPLY)
        # results = self.executor.exec_async(*cmds, flags=REPLY | SILENT)
        end_t = time.time()
        assert end_t - start_t < 4

        results2 = self.executor.exec_parallel(*cmds, flags=REPLY | DECODE)
        assert results2 == [(0, "", "{0}{0}".format(i)) for i in range(3, 0, -1)]
