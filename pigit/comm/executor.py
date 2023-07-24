from typing import (
    Callable,
    Coroutine,
    Optional,
    Tuple,
    Union,
    Dict,
    List,
    ByteString,
)
from subprocess import Popen, PIPE
import os
import sys
import copy
import contextlib
import asyncio


WAIT_ENTER = 1 << 0  # wait for enter-press afterwards. not support async.
DECODE = 1 << 1  # decoding the command result.
WAITING = 1 << 2  # waiting util to command ending.
REDIRECT = 1 << 3  # redirect output to the PIPE.
REPLY = 1 << 4  # fetch command result and return.
SILENT = 1 << 5  # silent mode. output will be discarded.

ExecResult = Tuple[int, Union[None, str, ByteString], Union[None, str, ByteString]]


class ExecFlag:
    """Flag ctx of ~Executor."""

    def __init__(
        self,
        reply: bool = False,
        silent: bool = False,
        decoding: bool = False,
        waiting: bool = False,
        wait_enter: bool = False,
    ) -> None:
        self.reply = reply
        self.silent = silent
        self.decoding = decoding
        self.waiting = waiting
        self.wait_enter = wait_enter


class Executor:
    def __init__(self, log_func: Optional[Callable] = None) -> None:
        self.log_func = log_func

    def _log(self, msg: str) -> None:
        """Log function"""

        if self.log_func is not None:
            with contextlib.suppress(Exception):
                self.log_func(msg)

    def _press_enter(self) -> None:
        """Wait for enter-press."""

        sys.stdout.write("Press ENTER to continue")
        input()

    def _preprocess_popen_kws(self, flags: int, popen_kws: Dict) -> "ExecFlag":
        """flags and popen_kws preprocess.

        Args:
            flags (int): flags of ~Executor.
            popen_kws (Dict): extra params of ~Popen.

        Returns:
            ExecFlag: flag ctx.
        """

        exec_flag = ExecFlag(decoding=bool(flags & DECODE))

        if flags & REPLY:
            exec_flag.reply = True

            # reply depend to waiting and redirect.
            flags |= REDIRECT
            flags |= WAITING

            if flags & WAIT_ENTER:
                exec_flag.wait_enter = True

        if flags & WAITING:
            exec_flag.waiting = True

        # redirect output to PIPE.
        if flags & REDIRECT:
            for key in ("stdout", "stderr"):
                popen_kws[key] = PIPE

        # output will be discarded.
        if flags & SILENT:
            devnull_writable = open(os.devnull, "w", encoding="utf-8")
            devnull_readable = open(os.devnull, "r", encoding="utf-8")

            popen_kws["stdin"] = devnull_readable
            for key in ("stdout", "stderr"):
                popen_kws[key] = devnull_writable

        return exec_flag

    def __call__(self, cmd: Union[str, List, Tuple], flags: int = 0, **kws) -> Tuple:
        return self.exec(cmd, flags, **kws)

    def exec(self, cmd: Union[str, List, Tuple], flags: int = 0, **kws) -> Tuple:
        """exec command with sync.
        Modify `kws` according to the options of `flags`, and `kws`
        will be transparently transmitted to ~Popen. In the same
        situation, the option priority of `flags` is higher than
        that of `kws` input parameters.

        Args:
            cmd (Union[str, List, Tuple]): command.
            flags (int, optional): exec flags. Defaults to 0.

        Returns:
            Tuple: result.
        """

        popen_kws = copy.deepcopy(kws)

        exec_flag = self._preprocess_popen_kws(flags, popen_kws)

        if "shell" not in popen_kws:
            popen_kws["shell"] = isinstance(cmd, str)

        popen_kws["args"] = cmd

        if not exec_flag.waiting:
            Popen(**popen_kws)
            return (None, None, None)
        else:
            try:
                # Take over the input stream and get the return information.
                with Popen(**popen_kws) as proc:
                    _out, _err = proc.communicate()
                    _code = proc.returncode
            except Exception as e:
                self._log(f"Failed to run: {cmd}\n{e}")
                return None, None, None
            else:
                if exec_flag.wait_enter:
                    self._press_enter()

                if exec_flag.decoding:
                    if _out is not None and not isinstance(_out, str):
                        _out = _out.decode()
                    if _err is not None and not isinstance(_err, str):
                        _err = _err.decode()

                if not exec_flag.reply:
                    if _out:
                        print(_out)
                    if _err:
                        print(_err)
                    return None, None, None

                return _code, _err, _out

    def exec_async(self, *cmds, flags: int = 0, **kws) -> List[Tuple]:
        """exec multi cmds with async.

        Args:
            flags (int, optional): exec flags. Defaults to 0.

        Returns:
            Any: _description_
        """

        popen_kws = copy.deepcopy(kws)

        exec_flag = self._preprocess_popen_kws(flags, popen_kws)

        popen_kws["shell"] = False  # shell must be False fro async
        popen_kws["start_new_session"] = True

        async def _async_cmd(*args, **kwargs) -> Tuple:
            # receive (program, *args, ...), so must split the full cmd,
            # and unpack incoming.
            proc = await asyncio.create_subprocess_exec(*args, **kwargs)

            if not exec_flag.waiting:
                return None, None, None

            _out, _err = await proc.communicate()
            if not exec_flag.reply:
                if _out:
                    print(_out.decode())
                if _err:
                    print(_err.decode())
                return None, None, None

            if proc.returncode != 0:
                return proc.returncode, args, None

            if exec_flag.decoding:
                return proc.returncode, _err.decode(), _out.decode()
            else:
                return proc.returncode, _err, _out

        async def _async_tasks(tasks: List[Coroutine]) -> List[ExecResult]:
            # The loop argument is deprecated since Python 3.8
            # and scheduled for removal in Python 3.10
            return await asyncio.gather(*tasks)

        # Generate tasks and run
        tasks: List[Coroutine] = []
        for cmd in cmds:
            if isinstance(cmd, str):
                tasks.append(_async_cmd(*cmd.split(), **popen_kws))
            else:
                tasks.append(_async_cmd(*cmd, **popen_kws))

        return asyncio.run(_async_tasks(tasks))
