import pytest
from .utils import analyze_it

from pigit import introduce
from pigit.git_utils import output_repository_info, output_git_local_config


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
