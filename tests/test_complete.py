import os
import pytest
from pprint import pprint
from .utils import analyze_it

from pigit import Git_Cmds, __project__, Parser
from pigit.shellcompletion import (
    ZshCompletion,
    BashCompletion,
    FishCompletion,
    process_argparse,
)


class TestCompletion:
    prog = "pigit"
    complete_vars = {key: value.get("help", "") for key, value in Git_Cmds.items()}
    script_dir = os.path.dirname(__file__)

    def test_error_complete_vars(self):
        with pytest.raises(TypeError):
            BashCompletion("test", "xxx", ".")

    def test_error_argparse_obj(self):
        with pytest.raises(TypeError):
            process_argparse("xxx")

        with pytest.raises(TypeError):
            process_argparse(object)

    def test_parse_parser(self):
        p = Parser()
        p.parse([""])
        res = process_argparse(p._parser)
        pprint(res)

    def print(self, c):
        print(c.prop)
        print(c.script_name)
        print(c.inject_path)

        source = c.generate_resource()
        print(source)

        c.write_completion(source)

    @analyze_it
    def test_bash(self):
        c = BashCompletion(self.prog, self.complete_vars, self.script_dir)
        self.print(c)

    def test_zsh(self):
        c = ZshCompletion(self.prog, self.complete_vars, self.script_dir)
        self.print(c)

        # print(c.inject_into_shell())

    def test_fish(self):
        c = FishCompletion(self.prog, self.complete_vars, self.script_dir)
        self.print(c)
