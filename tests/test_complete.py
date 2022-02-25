import os
import pytest
from pprint import pprint
from copy import deepcopy
from .utils import analyze_it

from pigit import Git_Cmds, __project__, Parser, argparse_dict
from pigit.shellcompletion import (
    ZshCompletion,
    BashCompletion,
    FishCompletion,
)


class TestCompletion:
    prog = "pigit"
    # complete_vars = {key: value.get("help", "") for key, value in Git_Cmds.items()}
    complete_vars = deepcopy(argparse_dict)
    cmd_temp = complete_vars["args"]["cmd"]["args"]
    cmd_temp.update({k: {"help": v["help"], "args": {}} for k, v in Git_Cmds.items()})
    script_dir = os.path.dirname(__file__)

    def test_error_complete_vars(self):
        with pytest.raises(TypeError):
            BashCompletion("test", "xxx", ".")

    def print(self, c):
        print(c.prog_name)
        print(c.script_name)
        print(c.inject_path)

        source = c.generate_resource()
        print(source)

        c.write_completion(source)

    @analyze_it
    def test_bash(self):
        c = BashCompletion(self.prog, self.complete_vars, self.script_dir)
        self.print(c)

    @analyze_it
    def test_zsh(self):
        c = ZshCompletion("pigit-dev", self.complete_vars, self.script_dir)
        self.print(c)

        # print(c.inject_into_shell())

    def test_fish(self):
        c = FishCompletion(self.prog, self.complete_vars, self.script_dir)
        self.print(c)
