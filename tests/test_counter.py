import sys

sys.path.insert(0, ".")

from pygittools import CodeCounter


def test_codecounter():
    CodeCounter.count_and_format_print()
