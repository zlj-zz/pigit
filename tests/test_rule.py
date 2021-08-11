import sys

sys.path.insert(0, ".")

import os
from pprint import pprint
from pigit.codecounter import CodeCounter


def test_regular_rule(path: str = os.getcwd()):
    ignore_dir = []
    counter = CodeCounter()
    for root, dirs, files in os.walk(path):

        # Process .gitignore to add new rule.
        counter.process_gitignore(root, files)

        # First, filter folder.
        is_effective_dir: bool = counter.matching(root)
        if not is_effective_dir:
            ignore_dir.append(full_path)
            continue

        for file in files:
            full_path: str = os.path.join(root, file)
            is_effective: bool = counter.matching(full_path)
            if is_effective:
                print(full_path)

    pprint(counter.Rules)
    print(ignore_dir)


if __name__ == "__main__":
    test_regular_rule(os.environ["HOME"] + "/.config")
