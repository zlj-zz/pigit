# -*- coding:utf-8 -*-

from typing import Dict, List, Literal, Optional, Tuple, Union, Any
import os, re, json, stat
import logging
import threading
import concurrent.futures
from shutil import get_terminal_size

from plenty.table import Table
from plenty import get_console

from .common.utils import confirm, get_file_icon, adjudgment_type


Logger = logging.getLogger(__name__)


CounterFormatType = Literal["simple", "table"]


class CodeCounter(object):
    """Class of statistical code.

    Attributes:
        Absolute_Rules (dict): Precompiled rules.
        Suffix_Type (dict): Supported file suffix dictionary.
        Special_Name (dict): Type dict of special file name.
            subscript, and the codes of different levels are colored
            when the results are output.
        symbol (dict):
    """

    # The default rule is to count only files. Ignore all video, audio, fonts, binaries.
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

    _Lock = threading.Lock()

    def __init__(
        self,
        *,
        count_path: Optional[str] = None,
        format_type: CounterFormatType = "table",
        use_ignore: bool = True,
        use_icon: bool = True,
        result_saved_path: str = "",
        whether_save: bool = True,
        color: bool = True,
        show_invalid: bool = False,
    ) -> None:
        """
        Args:
            count_path (str, optional): The path of needed count. Defaults to os.getcwd().
            use_ignore (bool, optional): Whether detect `.gitignore` file. Defaults to True.
            result_saved_path (str, optional): Result save path. Defaults to "".
            result_format (str, optional): Output format string. Defaults to "table".
            use_icon (bool, optional): Whether output with icon. Defaults to False.

        """
        # Store the rules obtained after processing.
        self.Rules: List = []

        self.count_path = count_path or os.getcwd()
        self.format_type = format_type
        self.use_ignore = use_ignore
        self.use_icon = use_icon
        self.result_saved_path = result_saved_path
        self.whether_save = whether_save
        self.color = color
        self.show_invalid = show_invalid

    def parse_gitignore2rule(self, root: str) -> None:
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
                self.Rules.append({"pattern": re.compile(item), "include": is_negative})

    def matching_rules(self, full_path: str) -> bool:
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

        # If multiple rules match successfully, we think the last rule added has
        # the highest priority. Or if just one, this no problem also.
        return res[-1]["include"]
        # selected_rule = max(res, key=lambda rule: len(str(rule["pattern"])))

    def _sub_count(self, root: str, files: List) -> tuple:
        """Process handle use by `self.count`."""
        show_invailed = self.show_invalid

        result: dict[str[dict[str, int]]] = {}  # type: dict[str,dict]
        valid_counter = invalid_counter = 0
        invalid_list: list[str] = []
        total_size: int = 0

        for file in files:
            full_path = os.path.join(root, file)
            is_effective = self.matching_rules(full_path)
            if is_effective:
                try:
                    # Try read size of the valid file. Then do sum calc.
                    file_size = os.path.getsize(full_path)
                    total_size += file_size
                except:
                    Logger.warn(f"Can't read size of '{full_path}'")

                # Get file type.
                file_type = adjudgment_type(file, original=True)
                try:
                    with open(full_path) as f:
                        count = len(f.read().split("\n"))
                except Exception:
                    if show_invailed:
                        invalid_list.append(file)
                    invalid_counter += 1
                    continue
                else:
                    # Superposition.
                    if result.get(file_type) is None:
                        result[file_type] = {"files": 1, "lines": count}
                    else:
                        result[file_type]["files"] += 1
                        result[file_type]["lines"] += count
                    valid_counter += 1

        return result, total_size, valid_counter, invalid_counter, invalid_list

    @staticmethod
    def _walk_err_callback(e):
        """Handle of processing walk error."""
        print("Walk error: {0}".format(e))
        return

    def count(self) -> Tuple[Dict, List, List]:
        """Statistics file and returns the result dictionary for Python3.

        Args:
            root_path (str): The path is walk needed.
            use_ignore (bool): Whether ignore files in `.gitignore`. Defaults to True.
            progress (bool): Whether show processing. Defaults to True.

        Return:
            result (dict): Dictionary containing statistical results.
            invalid_list (list): invalid file list.
            total_size (int): the sum size of all valid files.

            result = {
                'Python': {
                    'files': 5,
                    'lines': 2124,
                }
            }
        """
        root_path = self.count_path
        use_ignore = self.use_ignore

        result = {}  # type: dict[str,dict]
        data_count = [0, 0, 0]  # [total_size, valid_count, invalid_count]
        invalid_list = []  # Invalid file list.

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
                    if result.get(key) is None:
                        result[key] = values
                    else:
                        result[key]["files"] += _result[key]["files"]
                        result[key]["lines"] += _result[key]["lines"]

                data_count[0] += _total_size
                data_count[1] += _valid_counter
                data_count[2] += _invalid_counter
                invalid_list.extend(_invalid_list)

        cpu: int = os.cpu_count() or 1
        max_queue: int = cpu * 200
        print("Detect CPU count: {0}, start record ...".format(cpu))

        with concurrent.futures.ProcessPoolExecutor() as pool:
            for root, _, files in os.walk(root_path, onerror=self._walk_err_callback):
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
                if len(files) >= 15 and pool._queue_count < max_queue:
                    # Calling process.
                    future_result = pool.submit(self._sub_count, root, files)
                    future_result.add_done_callback(_callback)
                else:
                    (
                        _result,
                        _total_size,
                        _valid_counter,
                        _invalid_counter,
                        _invalid_list,
                    ) = self._sub_count(root, files)

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

        # Some processes may not be finished after synchronization.
        print("\nPlease wait calculate ...")

        return result, invalid_list, data_count[0]

    def _get_saved_path(self, root_path: str) -> str:
        file_name: str = (
            root_path.replace("/", "_").replace("\\", "_").replace(".", "_")
        )
        return os.path.join(self.result_saved_path, file_name)

    def load_recorded_result(self, root_path: str) -> Optional[Dict]:
        """Load count result."""
        file_path = self._get_saved_path(root_path)
        try:
            with open(file_path, "r") as rf:
                res = json.load(rf)
        except Exception:
            return None
        else:
            return res

    def save_result(self, result: Dict, root_path: str) -> bool:
        """Save count result.

        Generate name according to `root_path`, then try save the record
        result to [`TOOLS_HOME`/Counter].

        Args:
            result (dict): Statistical results.
            root_path (str): Traversal directory.

        Return:
            (bool): Whether saving successful.
        """

        file_path = self._get_saved_path(root_path)
        try:
            with open(file_path, "w" if os.path.isfile(file_path) else "x") as wf:
                json.dump(result, wf, indent=2)
        except Exception:
            return False
        else:
            return True

    def simple_output(self, result: Dict) -> str:
        gen = []
        for key, value in result.items():
            line = f"::{key}  (files:{value['files']:,} | lines:{value['lines']:,})"
            gen.append(line)

        return "\n".join(gen)

    def table_output(self, new: Dict, old: Dict) -> Table:
        use_icon = self.use_icon
        color = self.color

        tb = Table(title="[Code Counter Result]", title_style="bold")
        tb.add_column("Language")
        tb.add_column("Files")
        tb.add_column("Code lines")

        # Diff
        sum_lines = 0
        for key, value in new.items():
            files = value["files"]
            lines = value["lines"]
            # Calc sum code line.
            sum_lines += lines

            file_type_str = (
                "{0} {1}".format(get_file_icon(key), key) if use_icon else key
            )
            files_str = f"{files:,}"
            lines_str = f"{lines:,}"

            if color:
                file_type_str = f"`{file_type_str}`<cyan>"
                files_str = f"`{files_str}`<{self.color_index(files)}>"
                lines_str = f"`{lines_str}`<{self.color_index(lines)}>"

            # Compare change.
            if isinstance(old, dict) and old.get(key) is not None:
                old_files = old.get(key).get("files", None)
                old_lines = old.get(key).get("lines", None)

                if old_files and old_files != files:
                    files_change = "{:+}".format(files - old_files)
                else:
                    files_change = ""

                if old_lines and old_lines != lines:
                    lines_change = "{:+}".format(lines - old_lines)
                else:
                    lines_change = ""

            else:
                files_change = lines_change = ""

            if color:
                files_change_str = f"`{files_change}`<{'#98fb98' if files_change.startswith('+') else '#ff6347'}>"
                lines_change_str = f"`{lines_change}`<{'#98fb98' if lines_change.startswith('+') else '#ff6347'}>"
            else:
                files_change_str = files_change
                lines_change_str = lines_change

            tb.add_row(
                file_type_str,
                f"{files_str} {files_change_str}",
                f"{lines_str} {lines_change_str}",
            )

        # Print total and change graph.
        tb.caption = " Total: {0} lines".format(sum_lines)
        return tb

    @classmethod
    def color_index(
        cls, count: int, level_color: Union[List, Tuple, None] = None
    ) -> int:
        # Colors displayed for different code quantities.
        if level_color is None:
            level_color = (
                "green",
                "#EBCB8C",  # yellow
                "#FF6347",  # tomato
                "#C71585",  # middle violet red
                "#87CEFA",  # skyblue
            )
        index = len(str(count // 1000))
        return level_color[-1] if index > len(level_color) else level_color[index - 1]

    def generate_format_output(self, new: Dict, old: Optional[Dict] = None) -> Any:
        """Print result with color and diff.

        If the console width is not enough, the output is simple.

        Args:
            new (dict): Current statistical results.
            old (dict|None): The results saved in the past may not exist.
        """

        result_format = self.format_type

        needed_width: int = 67
        width, _ = get_terminal_size()
        if result_format == "simple" or width < needed_width:
            return self.simple_output(new)

        elif result_format == "table":
            return self.table_output(new, old)

    def run(
        self,
        whether_output: bool = True,
        *,
        count_path: Optional[str] = None,
        format_type: Optional[CounterFormatType] = None,
        use_ignore: Optional[bool] = None,
        use_icon: Optional[bool] = None,
        result_saved_path: Optional[str] = None,
        whether_save: Optional[bool] = None,
        color: Optional[bool] = None,
        show_invalid: Optional[bool] = None,
    ) -> None:
        if count_path is not None:
            self.count_path = count_path
        if format_type is not None:
            self.format_type = format_type
        if use_ignore is not None:
            self.use_ignore = use_ignore
        if use_icon is not None:
            self.use_icon = use_icon
        if result_saved_path is not None:
            self.result_saved_path = result_saved_path
        if whether_save is not None:
            self.whether_save = whether_save
        if color is not None:
            self.color = color
        if show_invalid is not None:
            self.show_invalid = show_invalid

        result, invalid_list, total_size = self.count()

        old_result = self.load_recorded_result(self.count_path)

        # diff print.
        if whether_output:
            output = self.generate_format_output(result, old_result)
            get_console().echo(output)

            if self.whether_save:
                self.save_result(result, self.count_path)
            if (
                self.show_invalid
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
            print("Files total size: {0:.2f}{1}".format(total_size, size_unit[i]))

        return result
