# -*- coding:utf-8 -*-

import os
import stat
import re
import json
import time
import logging
import threading
import concurrent.futures
from math import ceil
from shutil import get_terminal_size, register_unpack_format
from typing import Optional

from .utils import confirm
from .common import Color, Fx, Symbol
from .common.str_utils import shorten, get_file_icon, adjudgment_type
from .common.str_table import Table


Log = logging.getLogger(__name__)


class CodeCounterError(Exception):
    """CodeCounter error class."""

    pass


class CodeCounter(object):
    """Class of statistical code.

    Attributes:
        Absolute_Rules (dict): Precompiled rules.
        Suffix_Type (dict): Supported file suffix dictionary.
        Special_Name (dict): Type dict of special file name.
        level_color (list): Color list. The levels are calibrated by
            subscript, and the codes of different levels are colored
            when the results are output.
        symbol (dict):
        _support_format (list):
    """

    # The default rule is to count only files. Ignore all video, audio, fonts, binaries.
    Absolute_Rules: list[dict] = [
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

    # Colors displayed for different code quantities.
    level_color: list[str] = [
        "",
        Color.fg("#EBCB8C"),  # yellow
        Color.fg("#FF6347"),  # tomato
        Color.fg("#C71585"),  # middle violet red
        Color.fg("#87CEFA"),  # skyblue
    ]

    # Symbol corresponds to the desired color.
    symbol_color: dict = {"+": Color.fg("#98FB98"), "-": Color.fg("#FF6347")}

    # Supported output format.
    _support_format: list = ["table", "simple"]

    _Lock = threading.Lock()

    def __init__(
        self,
        count_path: str = os.getcwd(),
        use_ignore: bool = True,
        result_saved_path: str = "",
        result_format: str = "table",
        use_icon: bool = False,
    ) -> None:
        """
        Args:
            count_path (str, optional): The path of needed count. Defaults to os.getcwd().
            use_ignore (bool, optional): Whether detect `.gitignore` file. Defaults to True.
            result_saved_path (str, optional): Result save path. Defaults to "".
            result_format (str, optional): Output format string. Defaults to "table".
            use_icon (bool, optional): Whether output with icon. Defaults to False.

        Raises:
            CodeCounterError: when format string not right.
        """
        super(CodeCounter, self).__init__()

        # Store the rules obtained after processing.
        self.Rules: list = []

        self.count_path = count_path
        self.use_ignore = use_ignore
        self.result_saved_path = result_saved_path
        if result_format not in self._support_format:
            raise CodeCounterError(
                "Unsupported format, choice in {0}".format(self._support_format)
            )
        self.result_format = result_format
        self.use_icon = use_icon
        self.rune = Symbol.rune["bold"]

    def process_gitignore(self, root: str) -> None:
        """Process `.gitignore` files and add matching rules.

        Args:
            root (str): Absolute or relative path to the directory.
            files (list): The list of all file names under the `root` path.
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
            if confirm(
                "Can't read {0}, whether get jurisdiction[y/n]:".format(ignore_path)
            ):
                os.chmod(ignore_path, stat.S_IXGRP)
                os.chmod(ignore_path, stat.S_IWGRP)
                self.process_gitignore(root)
        except Exception as e:
            print("Read gitignore error: {0}".format(e))
        else:
            for item in ignore_content:
                is_negative = item[0] == "!"
                if is_negative:
                    item = item[1:]

                slash_index = item.find("/")
                if slash_index == 0:
                    item = root + item
                elif slash_index == -1 or slash_index == len(item) - 1:
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
                self.Rules.append({"pattern": re.compile(item), "include": is_negative})

    def matching(self, full_path: str) -> bool:
        """Matching rules.

        Judge whether it is the required file according to the rule matching path.
        Returns `True` if the file not needs to be ignored, or `False` if needs.

        Args:
            full_path (str): File full path for matching.
        """

        # Precompiled rules have the highest priority.
        if list(
            filter(lambda rule: rule["pattern"].search(full_path), self.Absolute_Rules)
        ):
            return False

        # Matching the generated rules.
        res = list(filter(lambda rule: rule["pattern"].search(full_path), self.Rules))
        if not res:
            return True
        else:
            # If multiple rules match successfully, we think the last rule added has
            # the highest priority. Or if just one, this no problem also.
            return res[-1]["include"]
            # selected_rule = max(res, key=lambda rule: len(str(rule["pattern"])))

    def _sub_count(self, root: str, files: list) -> tuple:
        """Process handle use by `self.count`."""
        result = {}  # type: dict[str,dict]
        valid_counter = invalid_counter = 0
        invalid_list = []
        total_size = 0

        for file in files:
            full_path = os.path.join(root, file)
            is_effective = self.matching(full_path)
            if is_effective:
                try:
                    # Try read size of the valid file. Then do sum calc.
                    size_ = os.path.getsize(full_path)
                    total_size += size_
                except:
                    Log.debug(f"Can't read size of '{full_path}'")

                # Get file type.
                type_ = adjudgment_type(file, original=True)
                try:
                    with open(full_path) as f:
                        count = len(f.read().split("\n"))
                except Exception:
                    invalid_counter += 1
                    invalid_list.append(file)
                    continue
                else:
                    # Superposition.
                    if result.get(type_, None) is None:
                        result[type_] = {"files": 1, "lines": count}
                    else:
                        result[type_]["files"] += 1
                        result[type_]["lines"] += count
                    valid_counter += 1
                finally:
                    pass

        return result, total_size, valid_counter, invalid_counter, invalid_list

    @staticmethod
    def _walk_err_callback(e):
        """Handle of processing walk error."""
        print("Walk error: {0}".format(e))
        raise SystemExit(0)

    def count(
        self, root_path: str, use_ignore: bool = True, progress: bool = True
    ) -> tuple[dict, list, int]:
        """Statistics file and returns the result dictionary for Python3.

        Args:
            root_path (str): The path is walk needed.
            use_ignore (bool): Whether ignore files in `.gitignore`. Defaults to True.
            progress (bool): Whether show processing. Defaults to True.

        Return:
            result (dict): Dictionary containing statistical results.
            invalid_list (list): invalid file list.
            total_size (int): the sum size of all valid files.

        >>> result = {
        ...     'py': {
        ...         'files': 5,
        ...         'lines': 2124,
        ...     }
        ... }
        >>> CodeCounter().count('~/.config', use_ignore=True)
        """

        if progress:
            width, _msg = self._get_ready()

        result = {}  # type: dict[str,dict]
        data_count = [0, 0, 0]  # [total_size, valid_count, invalid_count]
        invalid_list = []

        def _callback(r):
            (
                _result,
                _total_size,
                _valid_counter,
                _invalid_counter,
                _invalid_list,
            ) = r.result()

            with self._Lock:
                for key, values in _result.items():
                    if result.get(key, None) is None:
                        result[key] = values
                    else:
                        result[key]["files"] += _result[key]["files"]
                        result[key]["lines"] += _result[key]["lines"]

                data_count[0] += _total_size
                data_count[1] += _valid_counter
                data_count[2] += _invalid_counter
                invalid_list.extend(_invalid_list)

            if progress:
                pass
                # print(
                #     _msg.format(data_count[1], data_count[2]),
                #     end="",
                # )

        cpu: int = os.cpu_count() or 1
        max_queue = cpu * 200
        print("Detect CPU count: {0}, start record ...".format(cpu))

        with concurrent.futures.ProcessPoolExecutor() as pool:
            for root, _, files in os.walk(root_path, onerror=self._walk_err_callback):

                # First judge whether the directory is valid. Invalid directories
                # do not traverse files.
                is_effective_dir = self.matching(root)
                if not is_effective_dir:
                    continue

                # Process .gitignore file, add custom rules.
                if use_ignore and ".gitignore" in files:
                    self.process_gitignore(root)

                if not files:
                    continue

                # print(pool._queue_count)
                if len(files) >= 15 and pool._queue_count < max_queue:
                    # Calling process.
                    future_result = pool.submit(self._sub_count, root, files)
                    future_result.add_done_callback(_callback)
                else:
                    for file in files:
                        full_path = os.path.join(root, file)
                        is_effective = self.matching(full_path)
                        if is_effective:
                            try:
                                # Try read size of the valid file. Then do sum calc.
                                size_ = os.path.getsize(full_path)
                                with self._Lock:
                                    data_count[0] += size_
                            except:
                                Log.debug(f"Can't read size of '{full_path}'")

                            # Get file type.
                            type_ = adjudgment_type(file, original=True)
                            try:
                                with open(full_path) as f:
                                    count = len(f.read().split("\n"))
                            except Exception:
                                with self._Lock:
                                    data_count[2] += 1
                                    invalid_list.append(file)
                                continue
                            else:
                                # Superposition.
                                with self._Lock:
                                    if result.get(type_, None) is None:
                                        result[type_] = {"files": 1, "lines": count}
                                    else:
                                        result[type_]["files"] += 1
                                        result[type_]["lines"] += count
                                    data_count[1] += 1
                            finally:
                                if progress:
                                    # print(
                                    #     _msg.format(data_count[1], data_count[2]),
                                    #     end="",
                                    # )
                                    pass
            print("\nPlease wait calculate ...")

        if progress:
            print("")
        return result, invalid_list, data_count[0]

    def _get_ready(self) -> tuple[int, str]:
        width, _ = get_terminal_size()
        if width > 55:
            _msg = "\rValid files found: {:,}, Invalid files found: {:,}"
        else:
            _msg = "\r:: [{:,} | {:,}]"
        return width, _msg

    def _get_file_path(self, root_path: str) -> str:
        file_name: str = (
            root_path.replace("/", "_").replace("\\", "_").replace(".", "_")
        )
        return os.path.join(self.result_saved_path, file_name)

    def load_recorded_result(self, root_path: str) -> Optional[dict]:
        """Load count result."""
        file_path = self._get_file_path(root_path)
        try:
            with open(file_path) as rf:
                res = json.load(rf)
        except Exception:
            return None
        else:
            return res

    def save_result(self, result: dict, root_path: str) -> bool:
        """Save count result.

        Generate name according to `root_path`, then try save the record
        result to [`TOOLS_HOME`/Counter].

        Args:
            result (dict): Statistical results.
            root_path (str): Traversal directory.

        Return:
            (bool): Whether saving successful.
        """

        file_path = self._get_file_path(root_path)
        # ensure_path(CodeCounter.Result_Saved_Path)
        try:
            with open(file_path, "w" if os.path.isfile(file_path) else "x") as wf:
                json.dump(result, wf, indent=2)
        except Exception:
            return False
        else:
            return True

    @classmethod
    def color_index(cls, _count: int) -> int:
        _index = len(str(_count // 1000))
        if _index > len(cls.level_color):
            return -1
        else:
            return _index - 1

    def format_print(self, new: dict, old: Optional[dict] = None) -> None:
        """Print result with color and diff.

        If the console width is not enough, the output is simple.

        Args:
            new (dict): Current statistical results.
            old (dict|None): The results saved in the past may not exist.
        """

        result_format: str = self.result_format
        needed_width: int = 67
        width, _ = get_terminal_size()
        if result_format == "simple" or width < needed_width:
            for key, value in new.items():
                line = "::{} -> {:,} | {:,}".format(key, value["files"], value["lines"])
                print(line)
            return None

        elif result_format == "table":
            title = "[Code Counter Result]"
            header = ["Language", "Files", "Code lines"]

            # Print full time.
            print(time.strftime("%H:%M:%S %a %Y-%m-%d %Z", time.localtime()))

            # Diff
            sum_ = 0
            additions = 0
            deletions = 0
            tb_data = []
            for key, value in new.items():
                if self.use_icon:
                    key_display_str = "{0} {1}".format(get_file_icon(key), key)
                else:
                    key_display_str = key

                # Processing too long name.
                key_display_str = shorten(key_display_str, 20, front=False)

                # Set color.
                lines_color = self.level_color[self.color_index(value["lines"])]

                # Compare change.
                if isinstance(old, dict) and old.get(key, None) is not None:
                    old_files = old.get(key).get("files", None)
                    old_lines = old.get(key).get("lines", None)

                    if old_files and old_files != value["files"]:
                        files_change = "{:+}".format(value["files"] - old_files)
                        files_symbol = files_change[0]
                    else:
                        files_symbol = files_change = ""

                    if old_lines and old_lines != value["lines"]:
                        _change = value["lines"] - old_lines
                        lines_change = "{:+}".format(_change)
                        lines_symbol = lines_change[0]
                        if _change > 0:
                            additions += _change
                        else:
                            deletions -= _change
                    else:
                        lines_symbol = lines_change = ""

                else:
                    files_change = files_symbol = lines_change = lines_symbol = ""

                file_symbol = self.symbol_color.get(files_symbol, "")
                line_symbol = self.symbol_color.get(lines_symbol, "")
                tb_data.append(
                    [
                        f" {key_display_str:<21}",
                        f" {Fx.i}{value['files']:<11}{Fx.rs} {file_symbol}{files_change:>5}{Fx.rs}",
                        f" {Fx.i}{value['lines']:<15}{Fx.rs} {line_symbol}{lines_change:>6}{Fx.rs}",
                    ]
                )

                # Clac sum code line.
                sum_ += value["lines"]

            # Print table.
            tb = Table(header, tb_data, title=title)
            tb.print()

            # Print total and change graph.
            print(" Total: {0}".format(sum_))

            # Additions and deletions are calculated by percentage,
            # and the base is the total number of last statistics.
            if additions > 0 or deletions > 0:
                # Get prev count sum.
                old_sum = sum([i["lines"] for i in old.values()])

                print(" Altered: ", end="")
                print(
                    "{0}{1}".format(
                        self.symbol_color["+"], "+" * ceil(additions / old_sum * 100)
                    ),
                    end="",
                )
                print(
                    "{0}{1}{2}".format(
                        self.symbol_color["-"],
                        "-" * ceil(deletions / old_sum * 100),
                        Fx.reset,
                    )
                )

    def count_and_format_print(self, if_save=True, show_invalid=False) -> None:
        result, invalid_list, total_size = self.count(self.count_path, self.use_ignore)

        old_result = self.load_recorded_result(self.count_path)

        # diff print.
        self.format_print(result, old_result)
        if if_save:
            self.save_result(result, self.count_path)
        if (
            show_invalid
            and invalid_list
            and confirm("Whether print invalid file list?[y/n]", default=False)
        ):
            print(invalid_list)

        # optimize size unit.
        size_unit = ["byte", "KB", "MB", "GB"]
        for i in range(3):
            if total_size >= 1024:
                total_size /= 1024
            else:
                break
        else:
            i = 3
        print(" Files total size: {0:.2f}{1}".format(total_size, size_unit[i]))
