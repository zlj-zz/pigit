import os, sys


_PIGIT_PATH = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, _PIGIT_PATH)

from pigit.interaction import tui_main

tui_main()
