import sys

sys.path.insert(0, ".")

import time
import pytest

from pigit.command_processor.interaction import InteractiveAdd, DataHandle


@pytest.fixture(scope="module")
def setup():
    return InteractiveAdd(), DataHandle(use_color=True)


def test_files_time(setup):
    ia, dh = setup
    sum_time = 0
    min_time = float("inf")
    for _ in range(1000):
        start = time.time()
        dh.get_status(100)
        used_time = time.time() - start
        min_time = min(used_time, min_time)
        sum_time += used_time

    print(
        f"test [get_status] 1000 times, Total time spent: {sum_time}, min time: {min_time} "
    )
