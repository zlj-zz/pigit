import pytest
from .utils import analyze_it

from pigit import Parser, introduce
from pigit.gitinfo import output_repository_info, output_git_local_config


@analyze_it
def test_info():
    introduce()

    output_repository_info()


def test_output_config_error():
    output_git_local_config("xxx")


def test_normal():
    output_git_local_config("normal")


def test_table():
    output_git_local_config("table")


def test_show_help():
    p = Parser()
    p.parse([""])
    p._parser.print_help()
