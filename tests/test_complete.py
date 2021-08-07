import sys
from pprint import pprint

sys.path.insert(0, ".")

from pigit import ShellCompletion, GitProcessor


def test_generater():
    for item in ShellCompletion.Supported_Shell:
        print(item)
        s = ShellCompletion(
            {key: value["help-msg"] for key, value in GitProcessor.Git_Options.items()},
            shell=item
        )
        pprint(s.generate_resource())
