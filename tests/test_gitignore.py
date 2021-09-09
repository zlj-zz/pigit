import sys

sys.path.insert(0, ".")

import pytest
from pigit import GitignoreGenetor


def test_fetch_gitignore():
    base_url = "https://github.com/github/gitignore/blob/master/%s.gitignore"
    name = "Python"

    handle = GitignoreGenetor()
    content = handle.get_html_from_url(base_url % name)
    assert not content or "<!DOCTYPE html>" in content

    if content:
        ignore_content = handle.parse_gitignore_page(content)
        print(ignore_content)
