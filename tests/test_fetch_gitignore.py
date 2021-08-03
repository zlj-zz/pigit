import sys

# import urllib2

sys.path.insert(0, ".")

from pygittools import GitignoreGenetor


def test_fetch_gitignore():
    base_url = "https://github.com/github/gitignore/blob/master/%s.gitignore"
    name = "Python"

    content = GitignoreGenetor.get_ignore_from_url(base_url % name)
    ignore_content = GitignoreGenetor.parse_gitignore(content)
    print(ignore_content)
