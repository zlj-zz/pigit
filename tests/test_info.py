import sys

sys.path.insert(0, ".")

from pyinstrument import Profiler

from pigit.git_utils import output_repository_info, output_git_local_config


def test_info():
    profiler = Profiler()

    with profiler:
        output_repository_info()
    profiler.print()

    with profiler:
        output_git_local_config()
    profiler.print()
