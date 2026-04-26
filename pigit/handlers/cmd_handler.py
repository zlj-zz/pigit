# -*- coding: utf-8 -*-
"""
Module: pigit/handlers/cmd_handler.py
Description: Handler for cmd subcommand.
Author: Zev
Date: 2026-04-10
"""

from typing import TYPE_CHECKING

from plenty import get_console

from ..git.cmds import GitCommandNew, CommandCategory

if TYPE_CHECKING:
    from ..cmdparse.parser import Namespace


class CmdHandler:
    """Handler for cmd subcommand."""

    def __init__(self):
        self._processor = GitCommandNew()
        self._console = get_console()

    @staticmethod
    def _handle_widget(shell: str) -> int:
        """Print shell widget code for picker integration.

        Args:
            shell: Target shell (bash, zsh, fish)

        Returns:
            Exit code
        """
        from ..cmdparse.completion.widgets import WIDGETS

        console = get_console()
        code = WIDGETS.get(shell)
        if not code:
            console.echo(f"Unsupported shell: {shell}")
            return 1
        console.echo(code)
        return 0

    def _run_picker(self, category=None, print_only=False) -> int:
        """Run interactive picker."""
        from ..git.cmds._picker import run_cmd_new_picker

        if category:
            try:
                CommandCategory(category)
            except ValueError:
                self._console.echo(f"`Unknown category: {category}`<tomato>")
                self._console.echo(
                    f"Valid categories: {', '.join(c.value for c in CommandCategory)}"
                )
                return 1

        exit_code, message = run_cmd_new_picker(
            self._processor,
            pick_alt_screen=True,
            category=category,
            print_only=print_only,
        )
        if message:
            self._console.echo(message)
        return exit_code

    def handle(self, args: "Namespace") -> int:
        """Handle cmd subcommand.

        Args:
            args: Parsed arguments

        Returns:
            Exit code
        """
        if args.pick_print is not None:
            category = None if args.pick_print is True else args.pick_print
            return self._run_picker(category, print_only=True)

        if args.pick:
            category = None if args.pick is True else args.pick
            return self._run_picker(category)

        if args.list or args.dangerous or args.type:
            if args.dangerous:
                help_text = self._processor.get_help(dangerous_only=True)
            elif args.type:
                try:
                    category = CommandCategory(args.type)
                    help_text = self._processor.get_help(category=category)
                except ValueError:
                    self._console.echo(f"`Unknown category: {args.type}`<tomato>")
                    self._console.echo(
                        f"Valid categories: {', '.join(c.value for c in CommandCategory)}"
                    )
                    return 1
            else:
                help_text = self._processor.get_help()
            self._console.echo(help_text)
            return 0

        if args.search:
            results = self._processor.search(args.search)
            if not results:
                self._console.echo(f"No commands found for: {args.search}")
                return 0

            self._console.echo(f"\nSearch results for '{args.search}':\n")
            for cmd_def in results:
                meta = cmd_def.meta
                dangerous_mark = "▲ " if meta.dangerous else "  "
                self._console.echo(f"  {dangerous_mark}{meta.short:<12} {meta.help}")
                if meta.examples:
                    for ex in meta.examples[:2]:
                        self._console.echo(f"               Example: {ex}")
            self._console.echo("")
            return 0

        if args.command:
            cmd_name = args.command[0]
            cmd_args = args.command[1:] if len(args.command) > 1 else []
            exit_code, output = self._processor.execute(cmd_name, cmd_args)
            if output:
                self._console.echo(output)
            return exit_code

        return self._run_picker()


# Backward-compatible alias
handle_widget = CmdHandler._handle_widget


def handle_cmd(args: "Namespace") -> int:
    """Entry point for cmd subcommand.

    Args:
        args: Parsed arguments

    Returns:
        Exit code
    """
    if args.widget:
        return CmdHandler._handle_widget(args.widget)

    handler = CmdHandler()
    return handler.handle(args)
