import os
import sys

_PIGIT_PATH = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, _PIGIT_PATH)

from pigit.entry import pigit

if __name__ == "__main__":
    pigit()

    # _args = ["cmd"] + sys.argv[1:]
    # print(_args)
    # pigit(_args)
