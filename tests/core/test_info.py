# -*- coding:utf-8 -*-
import pytest
from utils import analyze_it

from pigit.info import introduce, show_gitconfig
from pigit.termui.cli_output import get_console

console = get_console()


def test_introduce():
    print()
    console.echo(introduce())


def test_gitconfig():
    c = show_gitconfig()
    # c = GitConfig(format_type="normal")
    print()
    console.echo(c)


@analyze_it
def test():
    introduce()

    print()
    c = show_gitconfig()
    console.echo(c)
