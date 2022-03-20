import os, sys

_PIGIT_PATH = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, _PIGIT_PATH)

from pigit.entry import main

if __name__ == "__main__":
    main()
