# -*- coding: utf-8 -*-
"""
Module: tests/cli/test_git_lock_policy.py
Description: Every git pigit spawns is told not to take optional locks.
Author: Zev
Date: 2026-10-09
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile

import pytest

from paths import PROJECT_ROOT

from pigit.entry import _declare_git_policy
from pigit.ext.executor import DECODE, REPLY
from pigit.ext.executor_factory import get_executor

_VAR = "GIT_OPTIONAL_LOCKS"


def _shim_dir() -> tuple[str, str]:
    """Return (PATH dir, spawn log) with a git that records its env and refuses.

    Same shape as ``test_startup_perf.py``'s, with the environment recorded
    instead of the argv.
    """
    d = tempfile.mkdtemp(prefix="pigit-opl-")
    wrapper = os.path.join(d, "git")
    log = os.path.join(d, "git-spawn.log")
    with open(wrapper, "w") as f:
        f.write(f'#!/bin/sh\necho "OPL=${{{_VAR}:-unset}} $*" >> "$GIT_SPAWN_LOG"\n')
        f.write("exit 1\n")
    os.chmod(wrapper, 0o755)
    return d, log


def _pigit(args: list[str], *, cwd: str, shim: str, log: str) -> None:
    env = dict(os.environ)
    env["PATH"] = shim + os.pathsep + env["PATH"]
    env["GIT_SPAWN_LOG"] = log
    env.pop(_VAR, None)
    subprocess.run(
        [sys.executable, "-m", "pigit", *args],
        capture_output=True,
        env=env,
        cwd=cwd,
        timeout=60,
    )


def _spawned(log: str) -> list[str]:
    if not os.path.exists(log):
        return []
    with open(log) as f:
        return [line for line in f.read().splitlines() if line]


class TestDeclaredBeforeDispatch:
    """The policy has to be in place before the parser picks a callback.

    ``Parser.main`` runs either a subcommand callback or the root one, never
    both, so a policy installed inside a handler would miss every ``pigit cmd``
    and ``pigit repo`` invocation while still looking correct from the TUI.
    """

    def _env_without_the_var(self) -> dict[str, str]:
        env = dict(os.environ)
        env.pop(_VAR, None)
        return env

    def test_importing_the_entry_point_declares_it(self):
        proc = subprocess.run(
            [sys.executable, "-c",
             f"import pigit.entry, os; print(os.environ.get('{_VAR}'))"],
            capture_output=True,
            text=True,
            env=self._env_without_the_var(),
            cwd=PROJECT_ROOT,
        )
        assert proc.stdout.strip() == "0"

    def test_an_explicit_setting_is_left_alone(self):
        env = self._env_without_the_var()
        env[_VAR] = "1"
        proc = subprocess.run(
            [sys.executable, "-c",
             f"import pigit.entry, os; print(os.environ.get('{_VAR}'))"],
            capture_output=True,
            text=True,
            env=env,
            cwd=PROJECT_ROOT,
        )
        assert proc.stdout.strip() == "1"

    def test_a_subcommand_run_carries_it_to_git(self, tmp_path):
        """``pigit cmd w`` dispatches to a subcommand callback, which the root
        handler never runs. Its git child must still carry the policy."""
        repo = tmp_path / "repo"
        repo.mkdir()
        subprocess.run(
            ["git", "init", "-q", "-b", "main"], cwd=repo, check=True
        )
        shim, log = _shim_dir()
        _pigit(["cmd", "w"], cwd=str(repo), shim=shim, log=log)

        spawned = _spawned(log)
        assert spawned, "expected the cmd path to spawn git"
        assert all(line.startswith("OPL=0") for line in spawned), spawned


class TestChildrenInheritIt:
    def test_a_child_spawned_by_the_executor_sees_it(self, monkeypatch):
        monkeypatch.delenv(_VAR, raising=False)
        _declare_git_policy()

        _, _, out = get_executor().exec(
            [sys.executable, "-c",
             f"import os; print(os.environ.get('{_VAR}'))"],
            flags=REPLY | DECODE,
        )

        assert str(out).strip() == "0"

    def test_setdefault_does_not_overwrite(self, monkeypatch):
        monkeypatch.setenv(_VAR, "1")

        _declare_git_policy()

        assert os.environ[_VAR] == "1"


@pytest.mark.parametrize("argv", [["-v"], ["cmd", "--list"], ["repo", "ll"]])
def test_no_entry_path_loses_the_policy(argv):
    """Whatever the argv, an entry point that spawns git must not spawn it
    with the variable missing. Paths that spawn nothing are fine -- the point
    is that none of them spawns a *bare* git."""
    shim, log = _shim_dir()
    _pigit(argv, cwd=PROJECT_ROOT, shim=shim, log=log)
    assert all(line.startswith("OPL=0") for line in _spawned(log)), _spawned(log)
