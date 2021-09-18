import sys

sys.path.insert(0, ".")

from pyinstrument import Profiler

from pigit.git_utils import repository_info, git_local_config


def test_info():
    profiler = Profiler()

    with profiler:
        repository_info()
    profiler.print()

    with profiler:
        git_local_config()
    profiler.print()
