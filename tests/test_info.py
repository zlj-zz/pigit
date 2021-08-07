import sys

sys.path.insert(0, ".")

from pigit import repository_info, git_local_config


def test_info():
    repository_info()
    git_local_config()
