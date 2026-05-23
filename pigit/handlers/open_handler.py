"""
Module: pigit/handlers/open_handler.py
Description: Handler for the `open` subcommand.
Author: Zev
Date: 2026-05-23
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..cmdparse.parser import Namespace
    from ..context import Context


class OpenHandler:
    """``pigit open`` — open the current repo's remote URL in a browser."""

    def __init__(self, ctx: "Context") -> None:
        from ..termui.cli_output import get_console

        self.ctx = ctx
        self.console = get_console()

    def open_browser(self, args: "Namespace") -> None:
        remote_url = self.ctx.local_git.get_remote_url()
        if not remote_url:
            self.console.echo("@tomato(No remote URL found.)")
            return

        if args.branch:
            remote_url += f"/tree/{args.branch}"
        elif args.issue:
            remote_url += f"/issues/{args.issue}"
        elif args.commit:
            remote_url += f"/commit/{args.commit}"

        if args.print:
            self.console.echo(f"Remote URL: @sky_blue({remote_url})")
            return

        try:
            import webbrowser

            webbrowser.open(remote_url)
        except Exception as e:
            self.console.echo(f"@tomato(Failed to open the repo; {e})")
        else:
            self.console.echo("Successfully opened repo.")
