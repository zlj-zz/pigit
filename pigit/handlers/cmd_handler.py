# -*- coding:utf-8 -*-

from typing import TYPE_CHECKING, Dict, List

from ..const import EXTRA_CMD_MODULE_NAME, EXTRA_CMD_MODULE_PATH
from ..git import GitProxy, get_extra_cmds
from .base_handler import BaseHandler

if TYPE_CHECKING:
    from ..cmdparse.parser import Namespace
    from ..context import Context


class CmdHandler(BaseHandler):
    """``pigit cmd`` — short git commands, help, and optional shell mode."""

    def __init__(
        self,
        ctx: "Context",
        args: "Namespace",
        unknown: List[str],
    ) -> None:
        super().__init__(ctx)
        self.args = args
        self.unknown = unknown

    def execute(self) -> None:
        if self.config.repo_auto_append:
            repo_path, _repo_conf = self.repo.confirm_repo()
            self.repo.add_repos([repo_path])

        extra_cmd: Dict = {}
        extra_cmd.update(get_extra_cmds(EXTRA_CMD_MODULE_NAME, EXTRA_CMD_MODULE_PATH))

        git_processor = GitProxy(
            extra_cmds=extra_cmd,
            prompt=self.config.cmd_recommend,
            display=self.config.cmd_display,
        )

        if self.args.shell:
            from ..shell_mode import PigitShell

            PigitShell(git_processor).cmdloop()
            return

        if self.args.show_commands:
            self.console.echo(git_processor.get_help())
            return

        if self.args.command_type:
            self.console.echo(git_processor.get_help_by_type(self.args.command_type))
            return

        if self.args.types:
            self.console.echo(git_processor.get_types())
            return

        if self.args.command:
            short_cmd = self.args.command
            self.args.args.extend(self.unknown)
            self.console.echo(git_processor.do(short_cmd, self.args.args))
            return

        self.console.echo("`pigit cmd -h`<ok> for help.")
