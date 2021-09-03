from __future__ import print_function
import sys

sys.path.insert(0, ".")

import os
import time
import threading

import concurrent.futures
from pprint import pprint
from functools import wraps

from pigit.codecounter import CodeCounter
from pigit import COUNTER_PATH


def test_codecounter(path=os.getcwd()):
    start_t = time.time()
    CodeCounter(
        result_saved_path=COUNTER_PATH, count_path=path
    ).count_and_format_print()
    print(time.time() - start_t)


def _read_handle(root, files, counter):
    # print(counter.Rules)
    result_count = 0

    # First, filter folder.
    is_effective_dir = counter.matching(root)
    if not is_effective_dir:
        return

    for file in files:
        full_path = os.path.join(root, file)
        is_effective = counter.matching(full_path)
        if is_effective:
            # threading.Thread(target=_read_handle, args=(full_path,)).start()

            try:
                # Try read size of the valid file. Then do sum calc.
                size_ = os.path.getsize(full_path)
            except:
                pass
            try:
                with open(full_path) as f:
                    # do nothing.
                    result_count += len(f.read().split())
            except:
                pass
            pass
    return result_count


def test_regular_rule(path=os.getcwd()):
    progress = 0

    ignore_dir = []
    counter = CodeCounter()

    res_count = 0

    def _callback(r):
        nonlocal res_count
        res = r.result()
        if res:
            res_count += res

    start_t = time.time()

    with concurrent.futures.ProcessPoolExecutor() as pool:
        for root, dirs, files in os.walk(path):
            # Flag for large dir.
            progress += 1
            print("\r{0}".format(progress), end="")
            # print(threading.active_count())

            # Process .gitignore to add new rule.
            if ".gitignore" in files:
                counter.process_gitignore(root)

            future_result = pool.submit(_read_handle, root, files, counter)
            future_result.add_done_callback(_callback)

            # r = future_result.result()
            # if r:
            #     res_count += r

        # threading.Thread(target=_read_handle, args=(root, files)).start()

        """
        # First, filter folder.
        is_effective_dir: bool = counter.matching(root)
        if not is_effective_dir:
            ignore_dir.append(root)
            continue

        for file in files:
            full_path: str = os.path.join(root, file)
            is_effective: bool = counter.matching(full_path)
            if is_effective:

                try:
                    # Try read size of the valid file. Then do sum calc.
                    size_ = os.path.getsize(full_path)
                except:
                    pass
                try:
                    with open(full_path) as f:
                        # do nothing.
                        len(f.read().split())
                except:
                    pass
                pass
        """
    print("\nover")
    # pprint(counter.Rules)
    # print(ignore_dir)
    print(time.time() - start_t)
    print("total:", res_count)


"""
[just match root]
13.6025s

[record lines count]
use thread: 65.19s
no thread:  77.51s

[print content]
use thread: 570.698s
no thread:  569.579s

877.2
954.35
"""


def test_pure_walk(path=os.getcwd()):
    count = 0
    start_t = time.time()
    for root, dirs, files in os.walk(path):
        for _ in files:
            count += 1
            print("\r{0}".format(count), end="")
        # print(root, dirs, files)
    print("")
    print(time.time() - start_t)


if __name__ == "__main__":
    # test_regular_rule()
    # test_regular_rule(os.environ["HOME"] + "/.config")
    # test_regular_rule(os.environ["HOME"] + "/prog")
    # test_regular_rule(os.environ["HOME"])
    # test_pure_walk(os.environ["HOME"] + "/prog")
    # test_pure_walk(os.environ["HOME"])

    test_codecounter(os.environ["HOME"] + "/prog")

    pass
