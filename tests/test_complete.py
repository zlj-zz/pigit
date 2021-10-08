import argparse
import pytest
from pprint import pprint
from .utils import analyze_it

from pigit import Git_Cmds, __project__, Parser
from pigit.shell_completion import ShellCompletion, process_argparse


class TestCompletion:
    def test_error_complete_vars(self):
        with pytest.raises(TypeError):
            ShellCompletion("test", "xxx", ".")

    def test_error_shell(self):
        with pytest.raises(ValueError):
            ShellCompletion("test", {}, ".", shell="cmd")

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

    @analyze_it
    def test_generater(self):

        for item in ShellCompletion.Supported_Shell:
            print(item)
            complete_vars = {
                key: value.get("help", "") for key, value in Git_Cmds.items()
            }
            handle = ShellCompletion(
                __project__, complete_vars, shell=item, script_dir="."
            )
            pprint(handle.generate_resource())
