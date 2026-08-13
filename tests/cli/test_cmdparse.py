import pytest
import os

from paths import PROJECT_ROOT as _PIGIT_PATH
from utils import analyze_it

from pigit.cmdparse.completion.base import ShellCompletion, ShellCompletionError
from pigit.cmdparse.completion import (
    ZshCompletion,
    BashCompletion,
    FishCompletion,
    shell_complete,
)
from pigit.init import get_shell



def _inject_registry_commands(complete_vars):
    """Inject cmd_new registry commands into cmd completion, mirroring entry.py."""
    from pigit.git.cmds import get_registry, register_user_commands
    from pigit.git.cmds._completion_types import CompletionType

    register_user_commands()
    registry = get_registry()

    for cmd_def in registry.get_all():
        meta = cmd_def.meta
        if meta.arg_completion is None:
            arg_comp_value = ""
        elif isinstance(meta.arg_completion, list):
            arg_comp_value = meta.arg_completion[0].value if meta.arg_completion else ""
        else:
            arg_comp_value = meta.arg_completion.value

        cmd_entry = {
            "help": meta.help,
            "args": {},
            "arg_completion": arg_comp_value,
        }
        complete_vars["args"]["cmd"]["args"][meta.short] = cmd_entry

    for alias_name, target in registry.get_aliases().items():
        cmd_entry = {
            "help": f"Alias for {target}",
            "args": {},
            "arg_completion": "",
        }
        complete_vars["args"]["cmd"]["args"][alias_name] = cmd_entry


class TestCompletion:
    @classmethod
    def setup_class(cls):
        cls.prog = "pigit"
        cls.script_dir = os.path.join(_PIGIT_PATH, "docs")

        from pigit.entry import pigit

        cls.complete_vars = pigit.to_dict()
        _inject_registry_commands(cls.complete_vars)

    def test_error(self):
        # error complete_vars
        with pytest.raises(TypeError):
            BashCompletion("test", "xxx", ".")

        # error prog
        with pytest.raises(ShellCompletionError):
            BashCompletion(None, {}, ".")

    def print(self, c: ShellCompletion):
        assert c.prog_name == "pigit"

        assert c.script_name == f"pigit_{c.SHELL}_comp"

        source = c.generate_resource()
        # print(source)

        c.write_completion(source)

    def test_bash(self):
        c = BashCompletion(None, self.complete_vars, self.script_dir)
        self.print(c)

    @analyze_it
    def test_zsh(self):
        c = ZshCompletion("pigit", self.complete_vars, self.script_dir)
        self.print(c)

    def test_fish(self):
        c = FishCompletion(self.prog, self.complete_vars, self.script_dir)
        self.print(c)

    def test_get_shell(self):
        assert get_shell() in ["bash", "zsh", "fish", ""]

    def test_action(self):
        shell_complete(self.complete_vars, "bash", "xxx", ".", "./test.txt")

    def test_shell_complete_empty_shell_returns_empty(self):
        assert shell_complete(self.complete_vars, "") == ""
        assert shell_complete(self.complete_vars, None) == ""

    def test_shell_complete_unsupported_shell_returns_empty(self):
        assert shell_complete(self.complete_vars, "powershell") == ""
        assert shell_complete(self.complete_vars, "unknown") == ""
