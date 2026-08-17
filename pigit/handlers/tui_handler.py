from __future__ import annotations

from ..const import IS_FIRST_RUN
from ..ext.utils import confirm
from ..info import introduce
from ..termui.tty_io import UNSUPPORTED_PLATFORM_MSG, platform_supported
from .base_handler import BaseHandler


class TuiHandler(BaseHandler):
    """Default no-subcommand flow: optional first-run intro, then TUI."""

    def preprocess(self) -> bool:
        if not platform_supported():
            self.console.echo(UNSUPPORTED_PLATFORM_MSG)
            return False
        return True

    def execute(self) -> None:
        if IS_FIRST_RUN:
            introduce()
            if not confirm("Input `enter` to continue:"):
                return

        from ..app import PigitApplication

        PigitApplication(
            git_api=self.git_api,
            managed_repos=self.managed_repos,
            config=self.config.get().tui,
        ).run()
