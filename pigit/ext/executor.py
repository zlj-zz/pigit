import asyncio
import copy
import contextlib
import dataclasses
import os
import sys
from subprocess import Popen, PIPE
from typing import (
    Any,
    Callable,
    Coroutine,
    Final,
    Optional,
    Tuple,
    Union,
    Dict,
    List,
    ByteString,
)

# Type defined
ExecResult = Tuple[int, Union[None, str, ByteString], Union[None, str, ByteString]]
ExecResType = Union[None, str, ByteString]

# Const
WAIT_ENTER: Final = 1 << 0  # wait for enter-press afterwards. not support async.
DECODE: Final = 1 << 1  # decoding the command result.
WAITING: Final = 1 << 2  # waiting util to command ending.
REDIRECT: Final = 1 << 3  # redirect output to the PIPE.
REPLY: Final = 1 << 4  # fetch command result and return.
SILENT: Final = 1 << 5  # silent mode. output will be discarded.


def _detect_encoding(data:ByteString)->str:
    encodings = ['utf-8', 'gbk','latin-1','iso-8859-1']

    for encoding in encodings:
        try:
            #  TODO: It may be possible to decode, but the result is not correct.
            data.decode(encoding)
            return encoding
        except UnicodeDecodeError:
            continue

    return  ''


@dataclasses.dataclass
class ExecState:
    """State ctx of ~Executor."""

    reply: bool = False
    silent: bool = False
    decoding: bool = False
    waiting: bool = False
    wait_enter: bool = False


class Executor:
    def __init__(self, log_func: Optional[Callable] = None) -> None:
        self.log_func = log_func

    def _log(self, msg: str) -> None:
        """Log function

        Args:
            msg (str): The message to log.
        """
        if self.log_func is not None:
            with contextlib.suppress(Exception):
                self.log_func(msg)

    def _press_enter(self) -> None:
        """Wait for enter-press."""
        sys.stdout.write("Press ENTER to continue")
        input()

    def generate_popen_state(
        self, flags: int, popen_kws: Dict[str, Any]
    ) -> "ExecState":
        """Generate the state context for executing a command.

        Args:
            flags (int): The flags of the ~Executor.
            popen_kws (Dict): The extra params of the ~Popen.

        Returns:
            ExecState: The state ctx.
        """
        es = ExecState(decoding=bool(flags & DECODE))

        if flags & REPLY:
            es.reply = True

            # reply depend to waiting and redirect.
            flags |= REDIRECT
            flags |= WAITING

            if flags & WAIT_ENTER:
                es.wait_enter = True

        if flags & WAITING:
            es.waiting = True

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

        return es

    def _try_decode(self, content: ExecResType, state: "ExecState") -> ExecResType:
        """Try to decode the output if decoding is enabled.

        Args:
            output: The output to decode.
            state (ExecState): The state context.

        Returns:
            The decoded output if decoding is enabled, otherwise the original output.
        """
        if state.decoding and content is not None and not isinstance(content, str):
            try:
                return content.decode()
            except UnicodeDecodeError:
                # Default encoding may not is 'utf-8' on windows.
                return content.decode(_detect_encoding(content))
        else:
            return content

    def _print(self, out, err) -> None:
        """Print the output and error.

        Args:
            out: The output to print.
            err: The error to print.
        """
        if out:
            print(out)
        if err:
            print(err)

    def __call__(self, cmd: Union[str, List, Tuple], *, flags: int = 0, **kws) -> Tuple:
        return self.exec(cmd, flags=flags, **kws)

    def exec(self, cmd: Union[str, List, Tuple], *, flags: int = 0, **kws) -> Tuple:
        """Execute a command synchronously.
        Modify `kws` according to the options of `flags`, and `kws` will be transparently
        transmitted to ~Popen. In the same situation, the option priority of `flags` is
        higher than that of `kws` input parameters.

        Args:
            cmd (Union[str, List, Tuple]): The command to execute.
            flags (int, optional): The exec flags. Defaults to 0.

        Returns:
            Tuple: The result of the execution.
        """
        es = self.generate_popen_state(flags, kws)

        if "shell" not in kws:
            kws["shell"] = isinstance(cmd, str)

        kws["args"] = cmd

        if not es.waiting:
            Popen(**kws)
            return (None, None, None)
        else:
            try:
                # Take over the input stream and get the return information.
                with Popen(**kws) as proc:
                    _out, _err = proc.communicate()
                    _code = proc.returncode
            except Exception as e:
                self._log(f"Failed to run: {cmd}\n{e}")
                return None, None, None
            else:
                if es.wait_enter:
                    self._press_enter()

                _out = self._try_decode(_out, es)
                _err = self._try_decode(_err, es)

                if not es.reply:
                    self._print(_out, _err)
                    return None, None, None

                return _code, _err, _out

    async def create_async_subprocess(self, es: "ExecState", *args, **kwargs) -> Tuple:
        """Create an asynchronous subprocess.

        Args:
            es (ExecState): The state context.
            *args: The command arguments.
            **kwargs: The additional parameters.

        Returns:
            Tuple: The result of the subprocess execution.
        """
        proc = await asyncio.create_subprocess_exec(*args, **kwargs)

        if not es.waiting:
            return None, None, None

        _out, _err = await proc.communicate()

        if proc.returncode != 0:
            return proc.returncode, args, None

        _out = self._try_decode(_out, es)
        _err = self._try_decode(_err, es)

        if not es.reply:
            self._print(_out, _err)
            return None, None, None

        return proc.returncode, _err, _out

    async def exec_async(
        self,
        *cmds,
        orders: Optional[List[Dict[str, Any]]] = None,
        flags: int = 0,
        **kws,
    ) -> List[Tuple]:
        """Execute multiple commands asynchronously.

        Args:
            *cmds: The commands to execute.
            orders (Optional[List[Dict[str, Any]]]): The special parameters for each command.
                If repeated with `kws`, it will be overwritten `kws`.
            flags (int, optional): The execution flags. Defaults to 0.
             **kws: Additional parameters for all commands.

        Returns:
            List[Tuple]: The results of the command executions.
        """
        popen_orders = copy.deepcopy(orders) if orders is not None else []
        # len of order not enough, will completion.
        if len(popen_orders) < len(cmds):
            popen_orders.extend([{}] * (len(cmds) - len(popen_orders)))

        es = self.generate_popen_state(flags, kws)

        kws["shell"] = False  # shell must be False for async
        kws["start_new_session"] = True

        # Generate tasks.
        tasks: List[Coroutine] = []
        for i, cmd in enumerate(cmds):
            cur_kws = {**kws, **popen_orders[i]}

            if isinstance(cmd, str):
                tasks.append(self.create_async_subprocess(es, *cmd.split(), **cur_kws))
            else:
                tasks.append(self.create_async_subprocess(es, *cmd, **cur_kws))

        return await asyncio.gather(*tasks)

    def exec_parallel(
        self,
        *cmds,
        orders: Optional[List[Dict[str, Any]]] = None,
        flags: int = 0,
        **kws,
    ) -> List[Tuple]:
        """Execute multiple commands in parallel."""
        return asyncio.run(self.exec_async(*cmds, orders=orders, flags=flags, **kws))
