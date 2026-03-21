# -*- coding:utf-8 -*-

from ..const import IS_FIRST_RUN, IS_WIN
from ..ext.utils import confirm
from ..info import introduce
from .base_handler import BaseHandler


class TuiHandler(BaseHandler):
    """Default no-subcommand flow: optional first-run intro, then TUI."""

    def preprocess(self) -> bool:
        if IS_WIN:
            print("Not support windows now.")
            return False
        return True

    def execute(self) -> None:
        if IS_FIRST_RUN:
            introduce()
            if not confirm("Input `enter` to continue:"):
                return

        from ..app import App

        App().run()
