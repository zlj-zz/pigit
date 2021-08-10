import sys

sys.path.insert(0, ".")

from pigit.codecounter import CodeCounter
from pigit import PIGIT_HOME


def test_codecounter():
    saved_path = PIGIT_HOME + "/Counter"
    CodeCounter(result_saved_path=saved_path).count_and_format_print()
