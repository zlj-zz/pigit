"""
Module: pigit/git/api/_base.py
Description: Shared base for git API submodules, forwarding facade state.
Author: Zev
Date: 2026-08-13
"""

from __future__ import annotations


class _OpsBase:
    """Shared read access to the facade's executor/path/log.

    Submodules hold a reference to the facade rather than copying its state,
    so a later ``facade.path = ...`` assignment is visible to every submodule.
    """

    def __init__(self, api) -> None:
        self._api = api

    @property
    def executor(self):
        return self._api.executor

    @property
    def path(self):
        return self._api.path

    @property
    def log(self):
        return self._api.log
