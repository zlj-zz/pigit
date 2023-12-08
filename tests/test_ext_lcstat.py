from typing import Optional
import os
import time
from pathlib import Path

import pytest

from pigit.const import USER_HOME
from pigit.ext.lcstat import Counter


@pytest.mark.parametrize(
    "path",
    [
        os.getcwd(),
        Path(USER_HOME, ".config")
        # USER_HOME + "/.config",
        # *os.environ.values(),
    ],
)
def test_count(path: str):
    print(f"\n===Test pure walk ({path})===")
    start_t = time.time()
    cc = Counter(show_invalid=True)
    res = cc.count(path, True)
    print(f"Result spend time: {time.time() - start_t}")
    # print(res)


@pytest.mark.parametrize(
    "path",
    [
        os.getcwd(),
        # os.environ["HOME"] + "/.config",
        # *os.environ.values(),
    ],
)
def test_diff_count(path: str):
    print(f"\n===Test pure walk ({path})===")
    start_t = time.time()
    cc = Counter()
    # cc.run()
    # cc.run(format_type="simple")
    res = cc.diff_count(path, True)
    print(f"Result spend time: {time.time() - start_t}")
    print(res)
