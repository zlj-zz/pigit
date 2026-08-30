"""Global executor selection for subprocess-backed git and helpers.

Production uses :func:`get_executor` which builds a :class:`LocalExecutor`
(subclass of :class:`~pigit.ext.executor.Executor`) on first use. Tests may
:func:`set_executor` with a :class:`MockExecutor` or custom
:class:`ExecutorStrategy`, then :func:`reset_executor` to restore defaults.
"""

from __future__ import annotations

import copy
from abc import ABC, abstractmethod
from typing import Any
from collections.abc import Iterator

from typing import cast

from .executor import DECODE, Executor, ExecResult, REPLY

CmdT = str | list[Any] | tuple[Any, ...]


class ExecutorStrategy(ABC):
    """Minimal surface used by git helpers (sync path)."""

    @abstractmethod
    def exec(self, cmd: CmdT, *, flags: int = 0, **kws: Any) -> ExecResult: ...

    @abstractmethod
    def exec_parallel(
        self,
        *cmds: CmdT,
        orders: list[dict[str, Any]] | None = None,
        flags: int = 0,
        max_concurrent: int | None = None,
        **kws: Any,
    ) -> list[ExecResult]: ...

    def exec_stream(self, cmd: CmdT, **kws: Any) -> Iterator[str]:
        """Fallback: buffer full stdout via :meth:`exec` (tests and non-streaming strategies)."""
        _, err, out = self.exec(cmd, flags=REPLY | DECODE, **kws)
        if err:
            return
        if not out:
            return
        yield from cast(str, out).splitlines()


class LocalExecutor(Executor, ExecutorStrategy):
    """Default: real subprocess behavior, identical to :class:`Executor`."""


def _cmd_key(cmd: CmdT) -> str:
    if isinstance(cmd, str):
        return cmd
    return " ".join(str(x) for x in cmd)


class MockExecutor(ExecutorStrategy):
    """Test double: map string command keys to ``(code, err, out)`` results."""

    def __init__(
        self,
        responses: dict[str, ExecResult] | None = None,
        default: ExecResult = (0, "", ""),
    ) -> None:
        self.responses = dict(responses) if responses else {}
        self.default = default
        self.exec_calls: list[tuple[CmdT, int, dict[str, Any]]] = []
        self.parallel_calls: list[
            tuple[
                tuple[CmdT, ...],
                list[dict[str, Any]] | None,
                int,
                int | None,
                dict[str, Any],
            ]
        ] = []

    def exec(self, cmd: CmdT, *, flags: int = 0, **kws: Any) -> ExecResult:
        self.exec_calls.append((cmd, flags, dict(kws)))
        key = _cmd_key(cmd)
        if key in self.responses:
            return self.responses[key]
        return self.default

    def exec_parallel(
        self,
        *cmds: CmdT,
        orders: list[dict[str, Any]] | None = None,
        flags: int = 0,
        max_concurrent: int | None = None,
        **kws: Any,
    ) -> list[ExecResult]:
        self.parallel_calls.append((cmds, orders, flags, max_concurrent, dict(kws)))
        popen_orders = copy.deepcopy(orders) if orders is not None else []
        if len(popen_orders) < len(cmds):
            popen_orders.extend([{}] * (len(cmds) - len(popen_orders)))
        out: list[ExecResult] = []
        for i, cmd in enumerate(cmds):
            merged = {**kws, **popen_orders[i]}
            out.append(self.exec(cmd, flags=flags, **merged))
        return out


_executor: ExecutorStrategy | None = None


def get_executor() -> ExecutorStrategy:
    """Return the global executor, building the default on first use."""
    global _executor
    if _executor is None:
        _executor = LocalExecutor()
    return _executor


def set_executor(strategy: ExecutorStrategy | None) -> None:
    """Replace the global executor; ``None`` clears so the next call builds default."""
    global _executor
    _executor = strategy


def reset_executor() -> None:
    """Clear the global executor so the next :func:`get_executor` rebuilds it."""
    global _executor
    _executor = None
