import sys

sys.path.insert(0, ".")

import time
import pytest

from pigit.command_processor.interaction import InteractiveAdd


@pytest.fixture(scope="module")
def setup():
    return InteractiveAdd()


def test_files_time(setup):
    ia = setup
    sum_time = 0
    min_time = float("inf")
    for _ in range(1000):
        start = time.time()
        ia.get_status(100)
        used_time = time.time() - start
        min_time = min(used_time, min_time)
        sum_time += used_time

    print(
        f"test [get_status] 1000 times, Total time spent: {sum_time}, min time: {min_time} "
    )
