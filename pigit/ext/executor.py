import asyncio
import copy
import contextlib
import dataclasses
import logging
import os
import shlex
import sys
from subprocess import Popen, PIPE
from typing import (
    Any,
    ByteString,
    Dict,
    Final,
    Iterator,
    List,
    Optional,
    Tuple,
    Union,
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


def _detect_encoding(data: ByteString) -> str:
    encodings = ["utf-8", "gbk", "latin-1", "iso-8859-1"]

    for encoding in encodings:
        try:
            #  TODO: It may be possible to decode, but the result is not correct.
            data.decode(encoding)
            return encoding
        except UnicodeDecodeError:
            continue

    return ""


def _split_cmd_argv(cmd: str) -> List[str]:
    """Split one command line into argv for :func:`asyncio.create_subprocess_exec`.

    Args:
        cmd (str): Full command string (no shell metacharacters such as ``|``).

    Returns:
        List[str]: Argv tokens; on :exc:`ValueError` from :func:`shlex.split`, falls back to :meth:`str.split`.
    """
    try:
        return shlex.split(cmd, posix=(os.name != "nt"))
    except ValueError:
        return cmd.split()


@dataclasses.dataclass
class ExecState:
    """State ctx of ~Executor."""

    reply: bool = False
    silent: bool = False
    decoding: bool = False
    waiting: bool = False
    wait_enter: bool = False


class Executor:
    def __init__(self, log: Optional[logging.Logger] = None) -> None:
        self.log = log

    def _log_warning(self, msg: object, *args: object) -> None:
        """Emit a diagnostic line when a logger was configured.

        Args:
            msg (str): The message to log.
        """
        if self.log is not None:
            with contextlib.suppress(Exception):
                self.log.warning(msg, *args)

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

        ``kws`` is passed to :class:`subprocess.Popen` after applying ``flags``; flag bits
        override conflicting ``kws`` where applicable.

        Args:
            cmd (Union[str, List, Tuple]): The command to execute.
            flags (int, optional): Bit flags (:data:`WAITING`, :data:`REPLY`, etc.). Defaults to 0.
            **kws: Extra :class:`~subprocess.Popen` arguments (``cwd``, ``env``, ``shell``, …).

        Returns:
            Tuple: ``(code, err, out)`` when :data:`REPLY` is set; otherwise often ``(None, None, None)``.
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
                self._log_warning(f"Failed to run: {cmd}, {e}")
                return None, None, None
            else:
                if es.wait_enter:
                    self._press_enter()

                _out = self._try_decode(_out, es)
                _err = self._try_decode(_err, es)

                if not es.reply:
                    self._print(_out, _err)
                    return _code, _err, None

                return _code, _err, _out

    def exec_stream(
        self,
        cmd: Union[str, List, Tuple],
        *,
        flags: int = 0,
        **kws: Any,
    ) -> Iterator[str]:
        """Yield decoded stdout lines as they arrive (no trailing newline).

        Forces :data:`REDIRECT`, :data:`WAITING`, and :data:`DECODE`. Stderr is read
        after stdout EOF to avoid pipe back-pressure; non-zero exit is logged.

        Args:
            cmd: Same as :meth:`exec`.
            flags: Extra flag bits merged into the stream run (rarely needed).
            **kws: Passed to :class:`~subprocess.Popen` (``cwd``, ``shell``, …).

        Yields:
            str: One logical line per stdout read.
        """
        kws = dict(kws)
        if "shell" not in kws:
            kws["shell"] = isinstance(cmd, str)
        kws["args"] = cmd
        stream_flags = REDIRECT | WAITING | DECODE | flags
        es = self.generate_popen_state(stream_flags, kws)
        try:
            with Popen(**kws) as proc:
                if proc.stdout is None:
                    return
                for raw in proc.stdout:
                    decoded = self._try_decode(raw, es)
                    if isinstance(decoded, str):
                        yield decoded.rstrip("\r\n")
                    else:
                        chunk = (
                            decoded.rstrip(b"\r\n")
                            if isinstance(decoded, bytes)
                            else decoded
                        )
                        if isinstance(chunk, bytes):
                            yield chunk.decode("utf-8", errors="replace")
                        else:
                            yield str(chunk).rstrip("\r\n")
                err_raw = proc.stderr.read() if proc.stderr is not None else None
            code = proc.returncode
            if code not in (0, None):
                self._log_warning(f"exec_stream exited {code}: {cmd!r}")
            if err_raw:
                err_text = self._try_decode(err_raw, es)
                if err_text:
                    self._log_warning(f"exec_stream stderr: {err_text!r}")
        except Exception as e:
            self._log_warning(f"Failed to exec_stream: {cmd!r}\n{e}")

    def _asyncio_spawn_kw(self, cur_kws: Dict[str, Any]) -> Dict[str, Any]:
        """Build kwargs for :func:`asyncio.create_subprocess_exec` / shell helpers.

        Args:
            cur_kws (Dict[str, Any]): Merged popen-style kwargs.

        Returns:
            Dict[str, Any]: Allowed keys only, with ``start_new_session=True`` if unset.
        """
        allowed = ("stdin", "stdout", "stderr", "cwd", "env", "executable")
        sk = {k: cur_kws[k] for k in allowed if k in cur_kws}
        sk.setdefault("start_new_session", True)
        return sk

    async def run_async_subprocess(
        self,
        es: "ExecState",
        cmd: Union[str, List, Tuple],
        cur_kws: Dict[str, Any],
    ) -> Tuple:
        """Run one subprocess asynchronously.

        String commands default to ``shell=True`` (``create_subprocess_shell``), matching
        :meth:`exec`. With ``shell=False``, strings are split via :func:`_split_cmd_argv`
        and executed with ``create_subprocess_exec``.

        Args:
            es (ExecState): State from :meth:`generate_popen_state`.
            cmd (Union[str, List, Tuple]): Command line or argv sequence.
            cur_kws (Dict[str, Any]): Per-call kwargs (``cwd``, ``shell``, stdio handles, …).

        Returns:
            Tuple: Same shape as :meth:`exec` for the active flags.
        """
        use_shell = cur_kws["shell"] if "shell" in cur_kws else isinstance(cmd, str)
        sk = self._asyncio_spawn_kw(cur_kws)

        try:
            if use_shell and isinstance(cmd, str):
                proc = await asyncio.create_subprocess_shell(cmd, **sk)
            elif isinstance(cmd, str):
                parts = _split_cmd_argv(cmd)
                if not parts:
                    self._log_warning(f"Empty argv after split: {cmd!r}")
                    return (1, "", "") if es.reply else (None, None, None)
                proc = await asyncio.create_subprocess_exec(parts[0], *parts[1:], **sk)
            else:
                argv = list(cmd)
                if not argv:
                    self._log_warning("Empty argv for subprocess_exec")
                    return (1, "", "") if es.reply else (None, None, None)
                proc = await asyncio.create_subprocess_exec(argv[0], *argv[1:], **sk)
        except Exception as e:
            self._log_warning(f"Failed to run: {cmd}, {e}")
            return None, None, None

        if not es.waiting:
            return None, None, None

        _out, _err = await proc.communicate()
        _code = proc.returncode

        _out = self._try_decode(_out, es)
        _err = self._try_decode(_err, es)

        if not es.reply:
            self._print(_out, _err)
            return None, None, None

        return _code, _err, _out

    async def exec_async(
        self,
        *cmds,
        orders: Optional[List[Dict[str, Any]]] = None,
        flags: int = 0,
        max_concurrent: Optional[int] = None,
        **kws,
    ) -> List[Tuple]:
        """Execute multiple commands concurrently (asyncio).

        Args:
            *cmds: Commands to run (each passed to :meth:`run_async_subprocess`).
            orders (Optional[List[Dict[str, Any]]]): Per-command kwargs; merged over ``kws``
                (later keys win).
            flags (int, optional): Shared flags for :meth:`generate_popen_state`. Defaults to 0.
            max_concurrent (Optional[int]): Max subprocesses at once; ``None`` means unlimited.
            **kws: Shared kwargs merged into each command before ``orders[i]``.

        Returns:
            List[Tuple]: One result per command, in the same order as ``cmds``.
        """
        popen_orders = copy.deepcopy(orders) if orders is not None else []
        # len of order not enough, will completion.
        if len(popen_orders) < len(cmds):
            popen_orders.extend([{}] * (len(cmds) - len(popen_orders)))

        es = self.generate_popen_state(flags, kws)

        n = len(cmds)
        sem: Optional[asyncio.Semaphore] = None
        if max_concurrent is not None and n > 0:
            mc = max(1, min(int(max_concurrent), n))
            sem = asyncio.Semaphore(mc)

        async def run_one(i: int) -> Tuple:
            cur_kws = {**kws, **popen_orders[i]}
            if sem is not None:
                async with sem:
                    return await self.run_async_subprocess(es, cmds[i], cur_kws)
            return await self.run_async_subprocess(es, cmds[i], cur_kws)

        return await asyncio.gather(*(run_one(i) for i in range(n)))

    def exec_parallel(
        self,
        *cmds,
        orders: Optional[List[Dict[str, Any]]] = None,
        flags: int = 0,
        max_concurrent: Optional[int] = None,
        **kws,
    ) -> List[Tuple]:
        """Run multiple commands in parallel (``asyncio.run`` + :meth:`exec_async`).

        Args:
            *cmds: Same as :meth:`exec_async`.
            orders (Optional[List[Dict[str, Any]]]): Same as :meth:`exec_async`.
            flags (int, optional): Same as :meth:`exec_async`. Defaults to 0.
            max_concurrent (Optional[int]): Same as :meth:`exec_async`.
            **kws: Same as :meth:`exec_async`.

        Returns:
            List[Tuple]: Same as :meth:`exec_async`.
        """
        return asyncio.run(
            self.exec_async(
                *cmds,
                orders=orders,
                flags=flags,
                max_concurrent=max_concurrent,
                **kws,
            )
        )
