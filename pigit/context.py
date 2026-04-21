# -*- coding:utf-8 -*-
"""Explicit runtime context

Uses :class:`contextvars.ContextVar` (not ``threading.local`` on a dataclass field) so
async and nested overrides behave predictably. CLI startup calls
:meth:`Context.install`; tests may use ``with Context(...)`` to shadow.
"""

from __future__ import annotations

import logging
from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .config import Config
    from .ext.executor_factory import ExecutorStrategy
    from .git.repo import Repo

_ctx_var: ContextVar[Optional["Context"]] = ContextVar("pigit_context", default=None)


@dataclass
class Context:
    """Holds primary services for one logical run (CLI process or test override)."""

    config: "Config"
    executor: "ExecutorStrategy"
    repo: "Repo"
    log: logging.Logger
    _token: Optional[Token] = field(default=None, init=False, repr=False)

    @staticmethod
    def try_current() -> Optional["Context"]:
        return _ctx_var.get()

    @staticmethod
    def current() -> "Context":
        c = _ctx_var.get()
        if c is None:
            raise RuntimeError(
                "No PigitContext is active; use Context.install() or "
                "'with Context(...):' before calling current()."
            )
        return c

    @staticmethod
    def install(ctx: "Context") -> None:
        """Attach context for this task (CLI: once at import / startup)."""
        _ctx_var.set(ctx)

    @staticmethod
    def detach() -> None:
        """Remove context for the current task (mainly for tests)."""
        _ctx_var.set(None)

    def __enter__(self) -> "Context":
        self._token = _ctx_var.set(self)
        return self

    def __exit__(self, *exc: object) -> None:
        if self._token is not None:
            _ctx_var.reset(self._token)
            self._token = None

    @classmethod
    def bootstrap(
        cls,
        *,
        config: "Config",
        repo_json_path: str,
        log_name: str = "pigit",
    ) -> "Context":
        """Build default context: logging, shared executor, :class:`Repo`, and named logger."""
        from .const import LOG_FILE_PATH
        from .ext.executor_factory import ExecutorFactory, LocalExecutor
        from .ext.log import logger, setup_logging
        from .git.repo import Repo

        setup_logging(
            debug=config.get().log.debug,
            log_file=None if config.get().log.output else LOG_FILE_PATH,
        )

        app_log = logger(log_name)
        executor = LocalExecutor(log=app_log)
        ExecutorFactory.set_strategy(executor)
        repo = Repo(repo_json_path=repo_json_path, executor=executor)
        return cls(
            config=config,
            executor=executor,
            repo=repo,
            log=app_log,
        )
