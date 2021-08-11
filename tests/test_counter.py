import sys

sys.path.insert(0, ".")

from pigit.codecounter import CodeCounter
from pigit import COUNTER_PATH


def test_codecounter():
    CodeCounter(result_saved_path=COUNTER_PATH).count_and_format_print()
