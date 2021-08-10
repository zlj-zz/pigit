import sys

# import urllib2

sys.path.insert(0, ".")

from pigit import GitignoreGenetor


def test_fetch_gitignore():
    base_url = "https://github.com/github/gitignore/blob/master/%s.gitignore"
    name = "Python"

    o = GitignoreGenetor()
    content = o.get_ignore_from_url(base_url % name)
    ignore_content = o.parse_gitignore_page(content)
    print(ignore_content)
