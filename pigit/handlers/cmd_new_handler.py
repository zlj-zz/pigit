# -*- coding: utf-8 -*-
"""
Module: pigit/handlers/cmd_new_handler.py
Description: Handler for cmd_new subcommand.
Author: Project Team
Date: 2026-04-10
"""

from typing import TYPE_CHECKING

from plenty import get_console

from ..git.cmds import GitCommandNew, CommandCategory

if TYPE_CHECKING:
    from ..cmdparse.parser import Namespace


console = get_console()


class CmdNewHandler:
    """Handler for cmd_new subcommand."""

    def __init__(self):
        self._processor = GitCommandNew()

    def handle(self, args: "Namespace") -> int:
        """Handle cmd_new subcommand.

        Args:
            args: Parsed arguments

        Returns:
            Exit code
        """
        # List commands
        if args.list or args.dangerous:
            if args.dangerous:
                help_text = self._processor.get_help(dangerous_only=True)
            elif args.type:
                try:
                    category = CommandCategory(args.type)
                    help_text = self._processor.get_help(category=category)
                except ValueError:
                    console.echo(f"Unknown category: {args.type}", style="red")
                    console.echo(f"Valid categories: {', '.join(c.value for c in CommandCategory)}")
                    return 1
            else:
                help_text = self._processor.get_help()
            console.echo(help_text)
            return 0

        # Search commands
        if args.search:
            results = self._processor.search(args.search)
            if not results:
                console.echo(f"No commands found for: {args.search}")
                return 0

            console.echo(f"\nSearch results for '{args.search}':\n")
            for cmd_def in results:
                meta = cmd_def.meta
                dangerous_mark = "⚠️ " if meta.dangerous else "  "
                console.echo(f"  {dangerous_mark}{meta.short:<12} {meta.help}")
                if meta.examples:
                    for ex in meta.examples[:2]:
                        console.echo(f"               Example: {ex}")
            console.echo("")
            return 0

        # Execute command
        if args.command:
            cmd_name = args.command[0]
            cmd_args = args.command[1:] if len(args.command) > 1 else []
            exit_code, output = self._processor.execute(cmd_name, cmd_args)
            if output:
                console.echo(output)
            return exit_code

        # Default: show help
        console.echo(self._processor.get_help())
        return 0


def handle_cmd_new(args: "Namespace") -> int:
    """Entry point for cmd_new subcommand.

    Args:
        args: Parsed arguments

    Returns:
        Exit code
    """
    handler = CmdNewHandler()
    return handler.handle(args)
