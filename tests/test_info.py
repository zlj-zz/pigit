import pytest
from .utils import analyze_it

from pigit import introduce
from pigit.info import output_repository_info, output_git_local_config


def test_introduce():
    introduce()


@analyze_it
def test_info():
    output_repository_info()


def test_output_config_error():
    output_git_local_config("xxx")


@analyze_it
def test_normal():
    output_git_local_config("normal")


@analyze_it
def test_table():
    output_git_local_config("table")
