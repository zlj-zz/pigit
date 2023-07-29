import contextlib
import copy
import json
import os
import re
import stat
import threading
from concurrent.futures import ProcessPoolExecutor
from typing import TYPE_CHECKING, Callable, Dict, List, Optional, Tuple

from .log import logger
from .utils import adjudgment_type, confirm

if TYPE_CHECKING:
    from concurrent.futures import Future


FILES_NUM = "1"
LINES_NUM = "2"
FILES_CHANGE = "3"
LINES_CHANGE = "4"

Absolute_Rules: List[Dict] = [
    # Exclude `.git` folder.
    {"pattern": re.compile(r"\.git$|\.git\/"), "include": False},
    {
        # Exclude all picture formats.
        "pattern": re.compile(
            r"\.xbm$|\.tif$|\.pjp$|\.svgz$|\.jpg$|\.jpeg$|\.ico$|\.icns$|\.tiff$|\.gif$|\.svg$|\.jfif$|\.webp$|\.png$|\.bmp$|\.jpeg$|\.avif$",
            re.I,
        ),
        "include": False,
    },
    {
        # Exclude all video formats.
        "pattern": re.compile(
            r"\.avi$|\.rmvb$|\.rm$|\.asf$|\.divx$|\.mpg$|\.mpeg$|\.mpe$|\.wmv$|\.mp4$|\.mkv$|\.vob$",
            re.I,
        ),
        "include": False,
    },
    {
        # Exclude all audio frequency formats.
        "pattern": re.compile(
            r"\.mp3$|\.wma$|\.mid[i]?$|\.mpeg$|\.cda$|\.wav$|\.ape$|\.flac$|\.aiff$|\.au$",
            re.I,
        ),
        "include": False,
    },
    {
        # Exclude all font formats.
        "pattern": re.compile(
            r"\.otf$|\.woff$|\.woff2$|\.ttf$|\.eot$",
            re.I,
        ),
        "include": False,
    },
    {
        # Exclude some binary file.
        "pattern": re.compile(
            r"\.exe$|\.bin$",
            re.I,
        ),
        "include": False,
    },
]

_Lock_Cache = {}


def default_walk_err_callback(e):
    """Default callback when has error on `walk`.

    Args:
        e (_type_): _description_
    """

    print("Walk error: {0}".format(e))


class CounterLockManageError(Exception):
    """Error class for ~CounterLockManage"""


class CounterLockManage:
    """Generate lock with multi ~Counter"""

    def __init__(self, obj: "Counter") -> None:
        self.id: int = id(obj)

    def __enter__(self):
        _Lock_Cache[self.id] = threading.Lock()

    def __exit__(self, exc_type, exc_val, exc_tb):
        del _Lock_Cache[self.id]

    @classmethod
    def get(cls, obj: "Counter"):
        lock = _Lock_Cache.get(id(obj))
        if lock is None:
            raise CounterLockManageError(f"Can not find lock with '{obj}'")

        return lock


class Counter:
    def __init__(
        self,
        walk_err_cb: Optional[Callable] = None,
        saved_dir: Optional[str] = None,
        show_invalid: bool = False,
    ) -> None:
        """
        Args:
            walk_err_cb (Optional[Callable], optional): Callback function when
                has walk error. Defaults to None.
            show_invalid (bool, optional): Whether show invalid files. Defaults to False.
        """
        self.rules = []

        self.walk_err_cb = (
            walk_err_cb if walk_err_cb is not None else default_walk_err_callback
        )

        self.saved_dir = saved_dir or ""
        self.show_invalid = show_invalid

        with contextlib.suppress(Exception):
            os.makedirs(self.saved_dir, exist_ok=True)

    def parse_gitignore2rule(self, root: str) -> None:
        """Process `.gitignore` files and add matching rules.

        Args:
            root (str): Absolute or relative path to the directory.
        """
        root = root.replace("\\", "/")  # Unified symbol.
        ignore_path = os.path.join(root, ".gitignore")

        try:
            with open(ignore_path) as f:
                ignore_content = filter(
                    # Filter out comment lines.
                    lambda x: x and not x.startswith("#"),
                    map(
                        # Filter out white space lines.
                        # Replace `\` to `/` for windows.
                        lambda x: x.strip().replace("\\", "/"),
                        # Read the file and split the lines.
                        f.read().split("\n"),
                    ),
                )
        except PermissionError:
            if confirm(f"Can't read {ignore_path}, whether get jurisdiction[y/n]:"):
                os.chmod(ignore_path, stat.S_IXGRP)
                os.chmod(ignore_path, stat.S_IWGRP)
                self.parse_gitignore2rule(root)
        except Exception as e:
            print(f"Read gitignore error: {e}")
        else:
            for item in ignore_content:
                is_negative = item[0] == "!"
                if is_negative:
                    item = item[1:]

                slash_index = item.find("/")
                if slash_index == 0:
                    item = root + item
                elif slash_index in [-1, len(item) - 1]:
                    item = "/".join([root, "**", item])
                else:
                    item = "/".join([root, item])

                item = re.sub(r"([\{\}\(\)\+\.\^\$\|])", r"\1", item)  # escape char
                item = re.sub(r"(^|[^\\])\?", ".", item)
                item = re.sub(r"\/\*\*", "([\\\\/][^\\\\/]+)?", item)  # /**
                item = re.sub(r"\*\*\/", "([^\\\\/]+[\\\\/])?", item)  # **/
                item = re.sub(r"\*", "([^\\\\/]+)", item)  # for `*`
                item = re.sub(r"\?", "*", item)  # for `?``
                item = re.sub(r"([^\/])$", r"\1(([\\\\/].*)|$)", item)
                item = re.sub(r"\/$", "(([\\\\/].*)|$)", item)  # for trialing with `/`
                self.rules.append({"pattern": re.compile(item), "include": is_negative})

    def matching_rules(self, full_path: str) -> bool:
        """Matching rules.

        Judge whether it is the required file according to the rule matching path.
        Returns `True` if the file not needs to be ignored, or `False` if needs.

        Args:
            full_path (str): File full path for matching.

        Returns:
            (bool): Whether the file is valid or not needs to be counted.
        """

        # Precompiled rules have the highest priority.
        if list(filter(lambda rule: rule["pattern"].search(full_path), Absolute_Rules)):
            return False

        # Matching the generated rules.
        res = list(filter(lambda rule: rule["pattern"].search(full_path), self.rules))

        # If multiple rules match successfully, we think the last rule added has
        # the highest priority. Or if just one, this no problem also.
        return res[-1]["include"] if res else True
        # selected_rule = max(res, key=lambda rule: len(str(rule["pattern"])))

    def count_files(
        self, root: str, files: List[str]
    ) -> Tuple[int, Dict[str, Dict[str, int]], List[str], int, int]:
        """Statistics files.

        Args:
            root (str): Absolute or relative path to the directory.
            files (List[str]): The list of all file names under the `root` path.

        Returns:
            Tuple[int, Dict, List[str], int, int]: total size of file,
                result dict, invalid file list, invalid file num, valid file num.
        """
        total_size = 0
        result = {}
        invalids = []
        invalid_num = 0
        valid_num = 0

        for file in files:
            full_path = os.path.join(root, file)

            if is_effective := self.matching_rules(full_path):
                try:
                    # Try read size of the valid file. Then do sum calc.
                    file_size = os.path.getsize(full_path)
                except Exception:
                    file_size = 0
                    logger(__name__).warn(f"Can't read size of '{full_path}'")

                total_size += file_size
                file_type = adjudgment_type(file, original=True)
                try:
                    with open(full_path) as f:
                        count = sum(1 for _ in f)

                        # Superposition.
                        if result.get(file_type) is None:
                            result[file_type] = {FILES_NUM: 1, LINES_NUM: count}
                        else:
                            result[file_type][FILES_NUM] += 1
                            result[file_type][LINES_NUM] += count

                        valid_num += 1
                except Exception:
                    invalid_num += 1

                    if self.show_invalid:
                        invalids.append(file)

                    continue

        return total_size, result, invalids, invalid_num, valid_num

    def update_dfd(self, src_d: Dict, d: Dict):
        if not d:
            return

        for k, v in d.items():
            if src_d.get(k) is None:
                src_d[k] = v
            else:
                v_type = type(v)

                if v_type == int:
                    src_d[k] += v
                elif v_type == list:
                    src_d[k].extend(v)
                elif v_type == dict:
                    self.update_dfd(src_d[k], v)

    def count_with_multiprocessing(
        self, root_path: str, use_ignore: bool
    ) -> Tuple[int, Dict[str, Dict[str, int]], List[str]]:
        """
        Args:
            root_path (str): The directory path to be counted.
            use_ignore (bool): Whether gitignore files in convenience
                directories need to be recognized, and rules generated.

        Returns:
            Tuple[int, Dict[str, Dict[str, int]], List]: total size,
                result dict, invalid file list.
        """
        total_size: int = 0
        result: Dict[str, Dict[str, int]] = {}
        invalids: List[str] = []
        invalid_num: int = 0
        valid_num: int = 0

        def _cb(r: "Future"):
            nonlocal total_size, result, invalids, invalid_num, valid_num
            (
                sub_total_size,
                sub_result,
                sub_invalids,
                sub_invalid_num,
                sub_valid_num,
            ) = r.result()

            with CounterLockManage.get(self):
                total_size += sub_total_size
                self.update_dfd(result, sub_result)
                invalids.extend(sub_invalids)
                invalid_num += sub_invalid_num
                valid_num += sub_valid_num

        max_queue: int = (os.cpu_count() or 1) * 50

        with CounterLockManage(self), ProcessPoolExecutor(
            max_workers=(os.cpu_count() or 1) + 4
        ) as pool:
            for root, _, files in os.walk(root_path, onerror=self.walk_err_cb):
                if not files:
                    continue

                # Judge whether the directory is valid. Invalid directories
                # do not traverse files.
                is_effective_dir = self.matching_rules(root)
                if not is_effective_dir:
                    continue

                # Process ``.gitignore`` file, add custom rules.
                if use_ignore and ".gitignore" in files:
                    self.parse_gitignore2rule(root)

                # If the number of files(exclude sub dir) in the directory is greater
                # than 15 and the number of enabled processes does not exceed the upper
                # limit, enable process traversal.
                # The `add_done_callback` method will execute the callback function in
                # a multi-threaded environment in the main process.
                if len(files) >= 15 or pool._queue_count < max_queue:
                    future_res = pool.submit(self.count_files, root, files)
                    future_res.add_done_callback(_cb)
                else:
                    self.count_files(root, files)

        return total_size, result, invalids

    def count(self, root_path: str, use_ignore: bool):
        return self.count_with_multiprocessing(root_path, use_ignore)

    def _saved_path(self, root_path: str) -> str:
        """Generate saved path."""
        file_name = root_path.replace("/", "_").replace("\\", "_").replace(".", "_")
        return os.path.join(self.saved_dir, file_name)

    def load(self, root_path: str) -> Dict[str, Dict[str, int]]:
        """Load count result."""
        file_path = self._saved_path(root_path)

        try:
            with open(file_path, "r") as f:
                res: Dict = json.load(f)
                return res
        except Exception:
            return {}

    def dump(self, root_path: str, result: Dict) -> bool:
        """Save count result.

        Args:
            root_path (str): Traversal directory.
            result (dict): Statistical result.

        Return:
            (bool): Whether saving successful.
        """
        file_path = self._saved_path(root_path)

        try:
            with open(file_path, "w" if os.path.isfile(file_path) else "x") as f:
                json.dump(result, f, indent=2)
                return True
        except Exception as e:
            logger(__name__).warning(f"Dump counter result with error: {e}")
            return False

    def diff_count(
        self, root_path: str, use_ignore: bool
    ) -> Tuple[str, Dict[str, Dict[str, int]], List[str]]:
        total_size, result, invalids = self.count(root_path, use_ignore)
        result_old = self.load(root_path)

        diff_result = {}
        for k, info in result.items():
            temp = diff_result[k] = copy.deepcopy(info)

            info_old = result_old.get(k)
            if info_old is not None:
                temp[FILES_CHANGE] = temp.get(FILES_NUM, 0) - info_old.get(FILES_NUM, 0)
                temp[LINES_CHANGE] = temp.get(LINES_NUM, 0) - info_old.get(LINES_NUM, 0)

        # update saved result.
        self.dump(root_path, result)

        # optimize size unit.
        size_unit = ["byte", "KB", "MB", "GB"]
        for i in range(3):
            if total_size >= 1024:
                total_size /= 1024
            else:
                break
        else:
            i = 3

        return "{0:.2f}{1}".format(total_size, size_unit[i]), diff_result, invalids
