import sys

sys.path.insert(0, ".")

from pigit import CodeCounter


def test_codecounter():
    CodeCounter.count_and_format_print()
