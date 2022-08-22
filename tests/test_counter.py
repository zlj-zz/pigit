# -*- coding:utf-8 -*-
from typing import Optional
import os, time
import pytest

from pigit.codecounter import CodeCounter


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
