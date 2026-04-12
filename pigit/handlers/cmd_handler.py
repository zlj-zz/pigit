# -*- coding:utf-8 -*-

import sys
from typing import TYPE_CHECKING

from ..const import CMD_TYPE_LIST_SENTINEL, EXTRA_CMD_MODULE_NAME, EXTRA_CMD_MODULE_PATH
from ..git import GitProxy, get_extra_cmds
from ..git.cmd_picker import run_command_picker
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
        unknown: list[str],
    ) -> None:
        super().__init__(ctx)
        self.args = args
        self.unknown = unknown

    def _exclusive_mode_labels(self) -> list[str]:
        """Human-readable labels for mutually exclusive ``cmd`` modes."""
        modes: list[str] = []
        if self.args.shell:
            modes.append("--shell")
        if getattr(self.args, "cmd_list", False):
            modes.append("-l/--list")
        if getattr(self.args, "cmd_search", None) is not None:
            modes.append("-s/--search")
        if getattr(self.args, "cmd_pick", False):
            modes.append("-p/--pick")
        if getattr(self.args, "cmd_type", None) is not None:
            modes.append("-t/--type")
        if self.args.command:
            modes.append("COMMAND")
        return modes

    def execute(self) -> None:
        if self.config.repo_auto_append:
            repo_path, _repo_conf = self.repo.confirm_repo()
            self.repo.add_repos([repo_path])

        extra_cmd: dict = {}
        extra_cmd.update(get_extra_cmds(EXTRA_CMD_MODULE_NAME, EXTRA_CMD_MODULE_PATH))

        git_processor = GitProxy(
            extra_cmds=extra_cmd,
            prompt=self.config.cmd_recommend,
            display=self.config.cmd_display,
        )

        modes = self._exclusive_mode_labels()
        if len(modes) > 1:
            self.console.echo(
                f"These options cannot be combined (pick one): {', '.join(modes)}.\n"
                "Use `pigit cmd -l` for the full table, `pigit cmd -s <query>` to search, "
                "or `pigit cmd -h` for help."
            )
            raise SystemExit(2)

        if self.args.shell:
            from ..shell_mode import PigitShell

            PigitShell(git_processor).cmdloop()
            return

        if getattr(self.args, "cmd_list", False):
            self.console.echo(git_processor.get_help())
            return

        search_bits = getattr(self.args, "cmd_search", None)
        if search_bits is not None:
            query = (search_bits[0] or "").strip()
            if not query:
                self.console.echo(
                    "`--search` / `-s` needs a non-empty QUERY.\n"
                    "Use `pigit cmd -l` for the full table, or "
                    "`pigit cmd -s <query>` with a keyword.\n"
                    "See `pigit cmd -h`."
                )
                raise SystemExit(2)
            text = git_processor.search_commands(query)
            if not text:
                self.console.echo(
                    f"No commands match {query!r}. Try `pigit cmd -l`, "
                    "a different keyword, or `pigit cmd --pick` in a TTY.\n"
                    "See `pigit cmd -h`."
                )
                raise SystemExit(1)
            self.console.echo(text)
            return

        if getattr(self.args, "cmd_pick", False):
            code, out = run_command_picker(
                git_processor,
                pick_alt_screen=getattr(self.args, "cmd_pick_alt_screen", False),
            )
            if code != 0:
                if out:
                    self.console.echo(out)
                raise SystemExit(code)
            if out is not None:
                self.console.echo(out)
            return

        cmd_type = getattr(self.args, "cmd_type", None)
        if cmd_type is not None:
            if cmd_type == CMD_TYPE_LIST_SENTINEL:
                self.console.echo(git_processor.get_types())
            else:
                self.console.echo(git_processor.get_help_by_type(cmd_type))
            return

        if self.args.command:
            short_cmd = self.args.command
            self.args.args.extend(self.unknown)
            self.console.echo(git_processor.do(short_cmd, self.args.args))
            return

        self.console.echo(
            "`pigit cmd -h`<ok> for help. \n"
            "Try `pigit cmd -l` for all short commands, \n"
            "`pigit cmd -s <query>` to search, \n"
            "`pigit cmd -t` for types, or `pigit cmd --pick` (TTY) to choose."
        )
