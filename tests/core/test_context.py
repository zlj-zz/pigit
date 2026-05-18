# -*- coding:utf-8 -*-

import logging

import pytest

from pigit.config import Config
from pigit.context import Context
from pigit.ext.executor_factory import ExecutorFactory, MockExecutor
from pigit.git.local_git import LocalGit
from pigit.git.managed_repos import ManagedRepos


@pytest.fixture(autouse=True)
def _isolate_context_and_factory():
    Context.detach()
    ExecutorFactory.reset()
    yield
    Context.detach()
    ExecutorFactory.reset()


def test_current_raises_without_context():
    assert Context.try_current() is None
    with pytest.raises(RuntimeError, match="No PigitContext"):
        Context.current()


def test_with_context_restores_previous():
    cfg = Config(path="/nonexistent/pigit-test.conf", version="0", auto_load=False)
    ex = MockExecutor()
    log = logging.getLogger("test_ctx")
    outer = Context(
        config=cfg,
        executor=ex,
        local_git=LocalGit(executor=ex),
        managed_repos=ManagedRepos(executor=ex),
        log=log,
    )

    Context.install(outer)
    assert Context.current() is outer

    inner_ex = MockExecutor(responses={"x": (0, "", "y")})
    inner = Context(
        config=cfg,
        executor=inner_ex,
        local_git=LocalGit(executor=inner_ex),
        managed_repos=ManagedRepos(executor=inner_ex),
        log=log,
    )

    with inner:
        assert Context.current() is inner
        assert Context.current().executor is inner_ex

    assert Context.current() is outer
    assert Context.current().executor is ex


def test_bootstrap_aligns_factory_and_repos():
    cfg = Config(path="/nonexistent/pigit-boot.conf", version="0", auto_load=False)
    ctx = Context.bootstrap(config=cfg, repo_json_path="/tmp/pigit-repos-test.json")
    assert ExecutorFactory.get() is ctx.executor
    assert ctx.local_git.executor is ctx.executor
    assert ctx.managed_repos.executor is ctx.executor
    assert isinstance(ctx.log, logging.Logger)
