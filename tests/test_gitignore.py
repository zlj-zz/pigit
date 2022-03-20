# -*- coding:utf-8 -*-
import pytest
from unittest.mock import patch
from .conftest import TEST_PATH
from .utils import analyze_it

from pigit.gitignore import GitignoreGenetor


handle = GitignoreGenetor()


@analyze_it
def test_fetch_gitignore():
    base_url = "https://github.com/github/gitignore/blob/main/%s.gitignore"
    name = "Python"

    content = handle.get_html_from_url(base_url % name)
    assert not content or "<!DOCTYPE html>" in content

    if content:
        ignore_content = handle.parse_gitignore_page(content)
        print(ignore_content)


@pytest.mark.parametrize(
    ("re_writting", "type_", "writting", "res_bool"),
    [
        ("y", "java", True, True),
        ("n", "c++", True, False),
        ("n", "go", False, True),
        ("y", "xxxx", True, False),
    ],
)
@patch("builtins.input")
def test_launch(mock_input, re_writting, type_, writting, res_bool):
    mock_input.return_value = re_writting
    assert handle.launch(type_, TEST_PATH, writting, "ignore_test") == res_bool
