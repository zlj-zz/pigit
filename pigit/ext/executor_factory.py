# -*- coding:utf-8 -*-
"""Global executor selection for subprocess-backed git and helpers.

Production uses :class:`LocalExecutor` (subclass of :class:`~pigit.ext.executor.Executor`).
Tests may :meth:`ExecutorFactory.set_strategy` with a :class:`MockExecutor` or custom
:class:`ExecutorStrategy`, then :meth:`ExecutorFactory.reset` to restore defaults.
"""

from __future__ import annotations

import copy
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple, Union

from .executor import Executor, ExecResult

CmdT = Union[str, List[Any], Tuple[Any, ...]]


class ExecutorStrategy(ABC):
    """Minimal surface used by git helpers (sync path)."""

    @abstractmethod
    def exec(self, cmd: CmdT, *, flags: int = 0, **kws: Any) -> ExecResult:
        ...

    @abstractmethod
    def exec_parallel(
        self,
        *cmds: CmdT,
        orders: Optional[List[Dict[str, Any]]] = None,
        flags: int = 0,
        max_concurrent: Optional[int] = None,
        **kws: Any,
    ) -> List[ExecResult]:
        ...


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
        responses: Optional[Dict[str, ExecResult]] = None,
        default: ExecResult = (0, "", ""),
    ) -> None:
        self.responses = dict(responses) if responses else {}
        self.default = default
        self.exec_calls: List[Tuple[CmdT, int, Dict[str, Any]]] = []
        self.parallel_calls: List[
            Tuple[Tuple[CmdT, ...], Optional[List[Dict[str, Any]]], int, Optional[int], Dict[str, Any]]
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
        orders: Optional[List[Dict[str, Any]]] = None,
        flags: int = 0,
        max_concurrent: Optional[int] = None,
        **kws: Any,
    ) -> List[ExecResult]:
        self.parallel_calls.append((cmds, orders, flags, max_concurrent, dict(kws)))
        popen_orders = copy.deepcopy(orders) if orders is not None else []
        if len(popen_orders) < len(cmds):
            popen_orders.extend([{}] * (len(cmds) - len(popen_orders)))
        out: List[ExecResult] = []
        for i, cmd in enumerate(cmds):
            merged = {**kws, **popen_orders[i]}
            out.append(self.exec(cmd, flags=flags, **merged))
        return out


class ExecutorFactory:
    _instance: Optional[ExecutorStrategy] = None

    @classmethod
    def reset(cls) -> None:
        cls._instance = None

    @classmethod
    def set_strategy(cls, strategy: Optional[ExecutorStrategy]) -> None:
        """Replace the global executor; ``None`` clears so next ``get()`` builds default."""
        cls._instance = strategy

    @classmethod
    def get(cls) -> ExecutorStrategy:
        if cls._instance is None:
            cls._instance = LocalExecutor()
        return cls._instance
