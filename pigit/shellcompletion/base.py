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
    _TEMPLATE: str  # script tempelate string.

    def __init__(
        self,
        prop: str,
        complete_vars: dict,
        script_dir: str,
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

        self.prop = prop

        if not isinstance(complete_vars, dict):
            raise TypeError("complete_var muse be dict.")
        self.complete_vars = complete_vars

        self.script_dir = script_dir
        self.script_name = script_name or "{0}_{1}_comp".format(self._SHELL, self.prop)
        self.inject_path = inject_path or self._INJECT_PATH

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
        script_src = self._TEMPLATE % {
            "prop": self.prop,
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
            Log.error(str(e) + str(e.__traceback__))
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
