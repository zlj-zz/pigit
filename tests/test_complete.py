import argparse
import pytest
from pprint import pprint
from .utils import analyze_it

from pigit import Git_Cmds, __project__
from pigit.shell_completion import ShellCompletion, process_argparse


def test_error():
    with pytest.raises(TypeError):
        ShellCompletion("test", "xxx", ".")

    with pytest.raises(ValueError):
        ShellCompletion("test", {}, ".", shell="cmd")

    with pytest.raises(TypeError):
        process_argparse("xxx")

    with pytest.raises(TypeError):
        process_argparse(object)


@analyze_it
def test_generater():

    for item in ShellCompletion.Supported_Shell:
        print(item)
        complete_vars = {key: value.get("help", "") for key, value in Git_Cmds.items()}
        handle = ShellCompletion(__project__, complete_vars, shell=item, script_dir=".")
        pprint(handle.generate_resource())
