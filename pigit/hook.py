# -*- coding: utf-8 -*-
"""
Module: pigit/hook.py
Description: Lifecycle hooks for pigit startup and shutdown.
Author: Zev
Date: 2026-05-21
"""

from __future__ import annotations


def before_hook(ctx) -> None:
    """Called after Context.bootstrap() on every command invocation.

    Handles auto_append: if the current working directory is a git repo
    and auto_append is enabled, adds/updates it in managed repos.
    """
    repo_path = ctx.local_git.confirm_repo()[0]
    if repo_path and ctx.config.get().repo.auto_append:
        try:
            ctx.managed_repos.add_repos([repo_path])
        except Exception:
            ctx.log.debug("auto_append failed", exc_info=True)


def after_hook(_ctx) -> None:
    """Called after command execution completes."""
    pass
