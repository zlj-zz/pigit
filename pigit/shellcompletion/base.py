# -*- coding:utf-8 -*-

import os
import re
import logging
from typing import Optional


Log = logging.getLogger(__name__)


class ShellCompletionError(Exception):
    """ShellCompletion error class."""

    pass


class ShellCompletion(object):
    """Implement and inject help classes for completion scripts."""

    _SHELL: str  # shell name.
    _INJECT_PATH: str  # script inject path.
    _template_source: str  # script tempelate string.

    def __init__(
        self,
        prog_name: str = None,
        complete_vars: dict = None,
        script_dir: str = None,
        script_name: Optional[str] = None,
        inject_path: Optional[str] = None,
    ) -> None:
        """Initialization.

        Args:
            prop (str): completion trigger command.
            complete_var (dict): complete arguments dict.
                >>> complete_vars = {
                ...     '-h': 'Display help messages',
                ...     '-v': 'Show version and exit',
                ... }
            script_dir (str): where is the completion file save.
            script_name (str, optional): completion file name. Defaults to None.
            inject_path (str, optional): script inject path.

        Raises:
            TypeError: when `complete_var` is not dict.
        """
        super(ShellCompletion, self).__init__()

        if not isinstance(complete_vars, dict):
            raise TypeError("complete_var muse be dict.")
        self.complete_vars = complete_vars

        if prog_name:
            self.prog_name = prog_name
        else:
            if prog_name := complete_vars.get("prog"):
                self.prog_name = prog_name
            else:
                raise ValueError("Can't get prog name anywhere.")

        self.script_dir = script_dir
        self.script_name = script_name or "{0}_{1}_comp".format(
            self.prog_name, self._SHELL
        )
        self.inject_path = inject_path or self._INJECT_PATH

    @property
    def func_name(self) -> str:
        """The name of the shell function defined by the completion
        script.
        """

        safe_name = re.sub(r"\W*", "", self.prog_name.replace("-", "_"), re.ASCII)
        return f"_{safe_name}_completion"

    def _parse(self, args: dict):
        _arguments = []
        _positions = []
        _sub_opts = {}

        for name, prop in args.items():
            if name == "-groups":
                for g_name, g_p in prop.items():
                    a, p, s = self._parse(g_p["args"])
                    _arguments.extend(a)
                    _positions.extend(p)
            elif name == "set_defaults":
                # Special need be ignore.
                pass
            elif "args" in prop:
                a, p, s = self._parse(prop["args"])
                _sub_opts[name] = {
                    "_arguments": a,
                    "_positions": p,
                    "_sub_opts": s,
                    "help": prop.get("help", "_"),
                }
            elif name.startswith("-"):
                _arguments.append((name, prop.get("help", "_")))
            else:
                _positions.append((name, prop.get("help", "_")))

        return _arguments, _positions, _sub_opts

    def generate(self):
        """Generate script content.

        Process self.complete_var to generate completion script content part.
        Due to different shells, the generated formats are different, which
        are finally implemented by subclasses.
        """

        raise NotImplementedError()

    def generate_resource(self) -> str:
        """Generate completion scirpt.

        Generate the completion script of the corresponding shell according to
        the template.

        Returns:
            (str): completion source.
        """

        complete_content = self.generate()
        script_src = self._template_source % {
            "func_name": self.func_name,
            "prop": self.prog_name,
            "complete_vars": complete_content,
        }

        return script_src

    def write_completion(self, complete_src: str) -> bool:
        """Save completion to config path.

        Args:
            complete_src (str): completion source.

        Returns:
            (str): completion full path.
        """

        if not os.path.isdir(self.script_dir):
            os.makedirs(self.script_dir, exist_ok=True)

        full_path = os.path.join(self.script_dir, self.script_name)

        try:
            with open(full_path, "w" if os.path.isfile(full_path) else "x") as f:
                for line in complete_src:
                    f.write(line)
        except Exception as e:
            Log.error(str(e))
            return False
        else:
            return True

    def inject_into_shell(self) -> bool:
        """Try using completion script.

        Inject the load of completion script into the configuration of shell.
        If it exists in the configuration, the injection will not be repeated.
        """

        full_script_path = os.path.join(self.script_dir, self.script_name)

        # Check whether already exist.
        try:
            with open(self.inject_path, "r") as f:
                shell_conf = f.read()
        except Exception as e:
            raise ShellCompletionError("Read shell config error: {0}".format(e))
        else:
            _re = re.compile(r"{}[^\s]*".format(full_script_path))
            files = _re.findall(shell_conf)

        injected = True if files else False

        if injected:
            return False

        try:
            # Inject.
            with open(self.inject_path, "a") as f:
                f.write("source %s" % (full_script_path))
        except Exception as e:
            raise ShellCompletionError(f"Inject error: {str(e)}")

        return True
