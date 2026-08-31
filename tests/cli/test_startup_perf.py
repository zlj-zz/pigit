# -*- coding: utf-8 -*-
"""
Module: tests/cli/test_startup_perf.py
Description: Startup optimizations — -v spawns no git, asyncio stays lazy.
Author: Zev
Date: 2026-08-31
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile

from paths import PROJECT_ROOT


def _blocking_git_dir() -> tuple[str, str]:
    """Return (PATH dir, spawn log) with a git wrapper that records and blocks."""
    d = tempfile.mkdtemp(prefix="pigit-nogit-")
    wrapper = os.path.join(d, "git")
    log = os.path.join(d, "git-spawn.log")
    with open(wrapper, "w") as f:
        f.write('#!/bin/sh\necho "git spawned: $@" >> "$GIT_SPAWN_LOG"\nexit 1\n')
    os.chmod(wrapper, 0o755)
    return d, log


def test_version_flag_spawns_no_git():
    """``-v`` must not run any git subprocess (deferred repo bootstrap)."""
    d, log = _blocking_git_dir()
    env = dict(os.environ)
    env["PATH"] = d + os.pathsep + env["PATH"]
    env["GIT_SPAWN_LOG"] = log
    proc = subprocess.run(
        [sys.executable, "-m", "pigit", "-v"],
        capture_output=True,
        env=env,
        cwd=PROJECT_ROOT,
    )
    assert proc.returncode == 0, proc.stderr.decode()
    assert b"Version" in proc.stdout
    assert not os.path.exists(log) or open(log).read() == ""


def test_asyncio_lazy_import_in_subprocess():
    """executor.py must not import asyncio until an async exec actually runs."""
    code = (
        "import sys; import pigit.ext.executor; "
        "assert 'asyncio' not in sys.modules, 'asyncio imported eagerly'"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, cwd=PROJECT_ROOT
    )
    assert proc.returncode == 0, proc.stderr.decode()
