import pytest
from .utils import analyze_it

from pigit.git_utils import get_repo_desc
from pigit.info import GitConfig, introduce
from pigit.render import echo


def test_introduce():
    echo()
    echo(introduce())


def test_info():
    echo(get_repo_desc())


def test_gitconfig():
    c = GitConfig()
    # c = GitConfig(format_type="normal")
    print()
    echo(c.generate())


@analyze_it
def test():
    introduce()
    get_repo_desc(color=False)

    c = GitConfig()
    c.format_type = "table"
    c.generate()
    c.format_type = "normal"
    c.generate()
