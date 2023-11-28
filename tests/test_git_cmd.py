import os
import pytest
from unittest.mock import patch

from pigit.git.proxy import GitProxy, get_extra_cmds
from pigit.git._cmd_func import add, set_email_and_username, fetch_remote_branch


class TestSCmd:
    def test_init_error(self):
        with pytest.raises(TypeError):
            GitProxy(extra_cmds="xxx")

    @pytest.fixture(scope="module")
    def setup(self):
        extra = {"aa": {"help": "print system user name."}}
        return GitProxy(extra_cmds=extra)

    @pytest.mark.parametrize(
        "command",
        [
            "git status",
            "git add xxx/xxx",
            "git checkout -b test",
            "git log --online --graph",
            "git log --dep 10 --online --graph",
            "git log --dep 10 --online --graph --color true",
            'git log --topo-order --stat --pretty=format:"%C(bold yellow)commit"',
        ],
    )
    def test_color_command(self, setup, command: str):
        from plenty import get_console

        console = get_console()
        handle = setup

        color_str = handle.color_command(command)
        console.echo(color_str)

    def test_load_extra_cmds(self):
        """Test load extra custom cmds."""

        name = "test_module"
        file = f"./{name}.py"
        with open(file, "w") as f:
            f.write("""extra_cmds = { 'A': 1 }""")

        d = get_extra_cmds(name, file)
        assert d["A"] == 1

        os.remove(file)


exec_patch = "pigit.git._cmd_func.Executor.exec"


class TestCmdFunc:
    @patch(exec_patch, return_value=None)
    def test_add(self, _):
        add([])

    @patch(exec_patch, return_value=None)
    def test_fetch_remote(self, _):
        fetch_remote_branch([])

    @pytest.mark.parametrize(
        "args",
        [
            (),
            ("--global",),
            ("global",),
            ("-g",),
        ],
    )
    @patch("builtins.input", return_value="abc@gmail.com")
    @patch(exec_patch, return_value=False)
    def test_set_ua(self, _a, _b, args):
        set_email_and_username(args)
