from typing import Optional
import os, time
import pytest

from pprint import pprint
from .utils import analyze_it

from pigit.codecounter import CodeCounter
from pigit.render import get_console


@pytest.mark.parametrize(
    "path",
    [
        None,
        os.getcwd(),
        # os.environ["HOME"] + "/.config",
        # *os.environ.values(),
    ],
)
def test_pure_walk(path: Optional[str]):
    print(f"\n===Test pure walk ({path})===")
    start_t = time.time()
    cc = CodeCounter(
        count_path=path,
        format_type="table",
        whether_save=False,
    )
    cc.run()
    cc.run(format_type="simple")
    print(f"Result spend time: {time.time() - start_t}")


"""
[just match root]
13.6025s

[record lines count]
use thread: 65.19s
no thread:  77.51s

[print content]
use thread: 570.698s
no thread:  569.579s

877.2
954.35
"""
