# -*- coding:utf-8 -*-

import os
import re
from typing import Dict, Optional, Tuple


class ShellCompletionError(Exception):
    """ShellCompletion error class."""

    pass


class ShellCompletion:
    """Implement and inject help classes for completion scripts."""

    SHELL: str  # shell name.
    TEMPLATE_SRC: str  # script template string.

    def __init__(
        self,
        prog_name: Optional[str] = None,
        complete_vars: Optional[Dict] = None,
        script_dir: Optional[str] = None,
        script_name: Optional[str] = None,
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

        Raises:
            TypeError: when `complete_var` is not dict.
        """

        if not isinstance(complete_vars, dict):
            raise TypeError("complete_var muse be dict.")
        self.complete_vars = complete_vars

        if prog_name is not None:
            self.prog_name = prog_name
        elif inner_prog_name := complete_vars.get("prog"):
            self.prog_name = inner_prog_name
        else:
            raise ShellCompletionError("Can't get prog name anywhere.") from None

        self.script_dir = script_dir or "."
        self.script_name = script_name or "{0}_{1}_comp".format(
            self.prog_name, self.SHELL
        )

    @property
    def func_name(self) -> str:
        """The name of the shell function defined by the completion
        script.
        """

        safe_name = re.sub(r"\W*", "", self.prog_name.replace("-", "_"), re.ASCII)
        return f"_{safe_name}_completion"

    def _parse(self, args: Dict) -> Tuple:
        _arguments = []
        _positions = []
        _sub_opts = {}

        for name, prop in args.items():
            prop_type = prop.get("type")

            if prop_type == "groups":
                a, p, s = self._parse(prop["args"])
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
                    "help": prop.get("help", "_").replace("\n", ""),
                }
            elif name.startswith("-"):
                _arguments.append((name, prop.get("help", "_").replace("\n", "")))
            else:
                _positions.append((name, prop.get("help", "_").replace("\n", "")))

        return _arguments, _positions, _sub_opts

    def generate_content(self):
        """Generate script content.

        Process self.complete_var to generate completion script content part.
        Due to different shells, the generated formats are different, which
        are finally implemented by subclasses.
        If this method is not overridden, a string of all commands will be generated.
        Like: '-h --help cmd repo'.
        """

        comp_keys = set()

        _arguments, _, _sub_opts = self._parse(self.complete_vars["args"])

        for _argument in _arguments:
            for handle in _argument[0].split():
                comp_keys.add(handle)

        sub_q = [_sub_opts]
        while sub_q:
            temp: Dict = sub_q.pop(0)
            for opt_name, p in temp.items():
                comp_keys.add(opt_name)

                if _arguments := p.get("_arguments"):
                    for _argument in _arguments:
                        for handle in _argument[0].split():
                            comp_keys.add(handle)

                if _opts := p.get("_sub_opts"):
                    sub_q.insert(-1, _opts)

        return " ".join(comp_keys)

    def generate_resource(self) -> str:
        """Generate completion script.

        Generate the completion script of the corresponding shell according to
        the template.

        Returns:
            (str): completion script source.
        """

        complete_content = self.generate_content()
        return self.TEMPLATE_SRC % {
            "func_name": self.func_name,
            "prop": self.prog_name,
            "complete_vars": complete_content,
        }

    def write_completion(self, complete_src: str) -> bool:
        """Save completion to target path.

        Args:
            complete_src (str): completion script source.

        Returns:
            (bool): whether saved.
        """

        if not os.path.isdir(self.script_dir):
            os.makedirs(self.script_dir, exist_ok=True)

        full_path = os.path.join(self.script_dir, self.script_name)

        try:
            with open(full_path, "w" if os.path.isfile(full_path) else "x") as f:
                for line in complete_src:
                    f.write(line)
        except Exception:
            return False
        else:
            return True
