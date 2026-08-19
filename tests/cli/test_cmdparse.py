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

    def test_to_dict_keys_cmd_positional_by_dest(self):
        """The cmd catch-all positional is dest ``command``, not an empty key."""
        from pigit.entry import pigit

        cmd_args = pigit.to_dict()["args"]["cmd"]["args"]
        assert "" not in cmd_args
        assert cmd_args["command"]["dest"] == "command"
        assert cmd_args["command"]["nargs"] == "*"

    def test_promote_does_not_lift_nested_command_completion(self):
        """Parent ``cmd`` must not inherit ``b.d``'s branch completer."""
        cmd = self.complete_vars["args"]["cmd"]
        assert ShellCompletion._promote_arg_completion(cmd) == ""
        assert ShellCompletion._promote_arg_completion(cmd["args"]["b.d"]) == "branch"
        rm = self.complete_vars["args"]["repo"]["args"]["rm"]
        assert ShellCompletion._promote_arg_completion(rm) == "repos"

    def test_zsh_cmd_tab_lists_shorts_not_branches(self):
        src = ZshCompletion("pigit", self.complete_vars).generate_resource()
        assert "cmd) _git_branches ;;" not in src
        assert "cmd) __cmd_values ;;" in src
        assert "b.d) _git_branches ;;" in src
        assert "i) _path_files -/" in src

    def test_bash_cmd_commands_are_shorts_not_the_positional(self):
        vars_ = BashCompletion("pigit", self.complete_vars).generate_content()
        commands = vars_["cmd_commands"].split()
        assert "command" not in commands
        assert "" not in commands
        assert "b" in commands
        assert "i" in commands
        assert "_git_branches" in vars_["cmd_arg_cases"]
        assert "_git_files" in vars_["cmd_arg_cases"] or "_git_files" in vars_[
            "helper_functions"
        ]

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
