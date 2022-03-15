# -*- coding:utf-8 -*-
import pytest
from .utils import analyze_it

from pigit.info import GitConfig, introduce
from pigit.render import echo


def test_introduce():
    echo()
    echo(introduce())


def test_gitconfig():
    c = GitConfig()
    # c = GitConfig(format_type="normal")
    print()
    echo(c.generate())


@analyze_it
def test():
    introduce()

    c = GitConfig()
    c.format_type = "table"
    c.generate()
    c.format_type = "normal"
    c.generate()
