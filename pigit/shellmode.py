from typing import TYPE_CHECKING, Callable, List, Optional, IO
import os, cmd
import functools

from plenty import get_console

if TYPE_CHECKING:
    from pigit.gitlib.processor import ShortGitter


class PigitShell(cmd.Cmd):
    intro: str = get_console().render_str(
        "b`Welcome come PIGIT shell.`<khaki>\n"
        "`You can use short commands directly. Input '?' to get help.`<khaki>\n"
    )
    prompt: str = "(pigit)> "

    def __init__(
        self,
        short_gitter: "ShortGitter",
        *,
        completekey: str = "tab",
        stdin: Optional[IO[str]] = None,
        stdout: Optional[IO[str]] = None,
    ) -> None:
        super().__init__(completekey, stdin, stdout)

        self.console = get_console()
        self.short_gitter = short_gitter

        for key, values in short_gitter.cmds.items():
            func_name = f"do_{key}"

            self.set_instance_method(self.make_fun(key, values.get("help")), func_name)

    # =================
    # cmd tools method
    # =================
    def make_fun(self, key: str, doc: str):
        _key = key

        def func(args: str):
            self.short_gitter.process_command(_key, args.split())

        func.__doc__ = doc

        return func

    @classmethod
    def set_instance_method(cls, func: Callable, func_name: Optional[str] = None):
        @functools.wraps(func)
        def dummy(self, *args, **kwargs):
            func(*args, **kwargs)

        if func_name is None:
            func_name = func.__name__

        setattr(cls, func_name, dummy)

    # ==================
    # print help method
    # ==================
    def default(self, line):
        """Called on an input line when the command prefix is not recognized.

        If this method is not overridden, it prints an error message and
        returns.

        """
        self.stdout.write(
            get_console().render_str(
                "`pigit shell: Invalid command '{0}', please select from`<error> "
                "`[shell, quit] or git short command.`<error>\n".format(line.split()[0])
            )
        )

    def do_help(self, arg: str):
        """List available commands with "help" or detailed help with "help cmd"."""
        if not arg:
            return super().do_help(arg)

        args: List[str] = arg.split()
        for a in args:
            self.stdout.write(f"{a}: ")
            super().do_help(a)

    # ================
    # support command
    # ================
    def do_shell(self, args: str):
        """Run a shell command.

        \rThis command is help you to run a normal terminal command in pigit shell.
        \rFor example, you can use `sh ls`<ok> to check the files of current dir.
        """
        os.system(args)

    do_sh = do_shell

    def do_all(self, args: str):
        """Show all short git cmds help."""
        self.short_gitter.print_help()
