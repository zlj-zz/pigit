import sys
from pprint import pprint

sys.path.insert(0, ".")

from pygittools import Completion


def test_generater():
    for item in Completion.Supported_Shell:
        pprint(Completion.generate_resource(item))
