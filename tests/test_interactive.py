import time
import textwrap
import pytest

from pigit.interaction.base import DataHandle
from pigit.interaction.status_interaction import InteractiveStatus


@pytest.fixture(scope="module")
def setup():
    return InteractiveStatus(), DataHandle(use_color=True)


def test_files_time(setup):
    ia, dh = setup

    status = dh.load_status(100)
    assert type(status) == list

    print("\nWill get 1000 times data.")
    sum_time = max_time = 0
    min_time = float("inf")
    for _ in range(1000):
        start = time.time()
        dh.load_status(100)
        used_time = time.time() - start
        min_time = min(used_time, min_time)
        max_time = max(used_time, max_time)
        sum_time += used_time

    print(
        textwrap.dedent(
            f"""
            test [get_status] 1000 times:
                Total spend time: {sum_time}
                Min spend time: {min_time}
                Max spend time: {max_time}
            """
        )
    )
