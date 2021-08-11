# -*- coding:utf-8 -*-

from __future__ import print_function, division
import os
import stat
import re
import json
import time
from math import ceil

from .compat import get_terminal_size
from .utils import confirm
from .str_utils import shorten
from .common import Color, Fx


class CodeCounterError(Exception):
    pass


class CodeCounter(object):
    """Class of statistical code.

    Attributes:
        Absolute_Rules (dict): Precompiled rules.
        Rules (dict): The dictionary for saving filtering rules.
            >>> one_rule = {
            ...     'pattern': re.compile(r''),
            ...     'include': False
            ... }
        Suffix_Type (dict): Supported file suffix dictionary.
        Special_Name (dict): Type dict of special file name.
        Level_Color (list): Color list. The levels are calibrated by
            subscript, and the codes of different levels are colored
            when the results are output.
        Result_Saved_Path (str): Directory to save and load results.
    """

    Absolute_Rules = [
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

    Rules = []

    Suffix_Types = {
        "": "",
        "c": "C",
        "conf": "Properties",
        "cfg": "Properties",
        "hpp": "C++",
        "cpp": "C++",
        "cs": "C#",
        "css": "CSS",
        "bat": "Batch",
        "dart": "Dart",
        "go": "Go",
        "gradle": "Groovy",
        "h": "C",
        "htm": "HTML",
        "html": "HTML",
        "java": "Java",
        "js": "Java Script",
        "jsx": "React",
        "json": "Json",
        "kt": "Kotlin",
        "less": "CSS",
        "lua": "Lua",
        "md": "Markdown",
        "markdown": "Markdown",
        "php": "PHP",
        "py": "Python",
        "plist": "XML",
        "properties": "Propertie",
        "ts": "Type Script",
        "tsx": "React",
        "rst": "reStructuredText",
        "sass": "CSS",
        "scss": "CSS",
        "sh": "Shell",
        "swift": "Swift",
        "vue": "Vue",
        "vim": "Vim Scirpt",
        "xml": "XML",
        "yaml": "YAML",
        "yml": "YAML",
        "zsh": "Shell",
        "dea": "XML",
        "urdf": "XML",
        "launch": "XML",
        "rb": "Ruby",
        "rs": "Rust",
        "rviz": "YAML",
        "srdf": "YAML",
        "msg": "ROS Message",
        "srv": "ROS Message",
    }

    Special_Names = {
        "requirements.txt": "Pip requirement",
        "license": "LICENSE",
    }

    Level_Color = [
        "",
        Color.fg("#EBCB8C"),  # yelllow
        Color.fg("#FF6347"),  # tomato
        Color.fg("#C71585"),  # middle violet red
        Color.fg("#87CEFA"),  # skyblue
    ]

    Symbol = {"+": Color.fg("#98FB98"), "-": Color.fg("#FF6347")}
    # Max_Thread = 10
    # Current_Thread = 0
    # Thread_Lock = threading.Lock()
    _support_format = ["table", "simple"]

    def __init__(
        self,
        count_path=os.getcwd(),
        use_ignore=True,
        result_saved_path="",
        result_format="table",
    ):
        super(CodeCounter, self).__init__()
        self.count_path = count_path
        self.use_ignore = use_ignore
        self.result_saved_path = result_saved_path
        if result_format not in self._support_format:
            raise CodeCounterError(
                "Unsupported format, choice in {}".format(self._support_format)
            )
        self.result_format = result_format

    def process_gitignore(self, root, files):
        """Process `.gitignore` files and add matching rules.

        Args:
            root (str): Absolute or relative path to the directory.
            files (list): The list of all file names under the `root` path.
        """

        root = root.replace("\\", "/")
        if ".gitignore" in files:
            try:
                ignore_path = os.path.join(root, ".gitignore")
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

                        item = re.sub(
                            r"([\{\}\(\)\+\.\^\$\|])", r"\1", item
                        )  # escape char
                        item = re.sub(r"(^|[^\\])\?", ".", item)
                        item = re.sub(r"\/\*\*", "([\\\\/][^\\\\/]+)?", item)  # /**
                        item = re.sub(r"\*\*\/", "([^\\\\/]+[\\\\/])?", item)  # **/
                        item = re.sub(r"\*", "([^\\\\/]+)", item)  # for `*`
                        item = re.sub(r"\?", "*", item)  # for `?``
                        item = re.sub(r"([^\/])$", r"\1(([\\\\/].*)|$)", item)
                        item = re.sub(
                            r"\/$", "(([\\\\/].*)|$)", item
                        )  # for trialing with `/`
                        self.Rules.append(
                            {"pattern": re.compile(item), "include": is_negative}
                        )
            except PermissionError:
                if confirm(
                    "Can't read {}, wether get jurisdiction[y/n]:".format(ignore_path)
                ):
                    os.chmod(ignore_path, stat.S_IXGRP)
                    os.chmod(ignore_path, stat.S_IWGRP)
                    self.process_gitignore(root, files)
            except Exception as e:
                print("Read gitignore error: {}".format(e))

    def matching(self, full_path):
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

    @classmethod
    def adjudgment_type(cls, file):
        """Get file type.

        First, judge whether the file name is special, and then query the
        file suffix. Otherwise, the suffix or name will be returned as is.

        Args:
            file (str): file name string.

        Returns:
            (str): file type.
        """

        pre_type = cls.Special_Names.get(file.lower(), None)
        if pre_type:
            return pre_type

        suffix = file.split(".")[-1]
        suffix_type = cls.Suffix_Types.get(suffix.lower(), None)
        if suffix_type:
            return suffix_type
        else:
            return suffix

    # @staticmethod
    # def count_file_thread(full_path):
    #     pass

    @staticmethod
    def _count_err_callback(e):
        """Handle of processing walk error."""
        print("Walk error: {}".format(e))
        raise SystemExit(0)

    def count(self, root_path=".", use_ignore=True, progress=False):
        """Statistics file and returns the result dictionary.

        Args:
            root_path (str): The path is walk needed.
            use_ignore (bool): Wether ignore files in `.gitignore`. Defaults to True.
            progress (bool): Wether show processing. Defaults to True.

        Return:
            result (dict): Dictionary containing statistical results.
            >>> result = {
            ...     'py': {
            ...         'files': 5,
            ...         'lines': 2124,
            ...     }
            ... }
            >>> CodeCounter.count('~/.config', use_ignore=True)
        """

        if progress:
            width, _ = get_terminal_size()
            if width > 55:
                _msg = "\rValid files found: {:,}, Invalid files found: {:,}"
            else:
                _msg = "\r:: [{:,} | {:,}]"

        result = {}
        valid_counter = 0
        invalid_counter = 0
        invalid_list = []
        for root, _, files in os.walk(
            root_path,
            onerror=self._count_err_callback,
        ):

            # First judge whether the directory is valid. Invalid directories
            # do not traverse files.
            is_effective_dir = self.matching(root)
            if not is_effective_dir:
                continue

            if use_ignore:
                self.process_gitignore(root, files)

            # TODO: Would it be better to use threads?
            for file in files:
                full_path = os.path.join(root, file)
                is_effective = self.matching(full_path)
                if is_effective:
                    # Get file type.
                    type_ = self.adjudgment_type(file)
                    try:
                        with open(full_path) as f:
                            count = len(f.read().split("\n"))

                        # Superposition.
                        if result.get(type_, None) is None:
                            result[type_] = {"files": 1, "lines": count}
                        else:
                            result[type_]["files"] += 1
                            result[type_]["lines"] += count
                        valid_counter += 1
                    except Exception as e:
                        invalid_counter += 1
                        invalid_list.append(file)
                        continue
                    finally:
                        if progress:
                            print(
                                _msg.format(valid_counter, invalid_counter),
                                end="",
                            )

        if progress:
            print("")
        return result, invalid_list

    def load_recorded_result(self, root_path):
        """Load count result."""
        file_name = root_path.replace("/", "_").replace("\\", "_").replace(".", "_")
        file_path = os.path.join(self.result_saved_path, file_name)
        try:
            with open(file_path) as rf:
                res = json.load(rf)
                return res
        except Exception:
            return None

    def save_result(self, result, root_path):
        """Save count result.

        Generate name according to `root_path`, then try save the record
        result to [`TOOLS_HOME`/Counter].

        Args:
            result (dict): Statistical results.
            root_path (str): Traversal directory.

        Return:
            (bool): Wether saving successful.
        """

        file_name = root_path.replace("/", "_").replace("\\", "_").replace(".", "_")
        file_path = os.path.join(self.result_saved_path, file_name)
        # ensure_path(CodeCounter.Result_Saved_Path)
        try:
            with open(file_path, "w" if os.path.isfile(file_path) else "x") as wf:
                json.dump(result, wf, indent=2)
                return True
        except Exception:
            return False

    @classmethod
    def color_index(cls, _count):
        _index = len(str(_count // 1000))
        if _index > len(cls.Level_Color):
            return -1
        else:
            return _index - 1

    def format_print(self, new, old=None):
        """Print result with color and diff.

        If the console width is not enough, the output is simple.

        Args:
            new (dict): Current statistical results.
            old (dict|None): The results saved in the past may not exist.
        """

        result_format = self.result_format
        needed_width = 67
        width, _ = get_terminal_size()
        if result_format == "simple" or width < needed_width:
            for key, value in new.items():
                line = "{}: {:,} | {:,}".format(key, value["files"], value["lines"])
                print(line)
            return

        elif result_format == "table":
            # Print full time.
            print(time.strftime("%H:%M:%S %a %Y-%m-%d %Z", time.localtime()))
            # Print title.
            print("{}{:^67}{}".format(Fx.bold, "[Code Counter Result]", Fx.unbold))
            # Print table header.
            print("=" * needed_width)
            print(
                "| {bold}{:<21}{unbold}| {bold}{:<17}{unbold}| {bold}{:<22}{unbold}|".format(
                    "Language", "Files", "Code lines", bold=Fx.bold, unbold=Fx.unbold
                )
            )
            print("|{sep:-<22}|{sep:-<18}|{sep:-<23}|".format(sep="-"))
            # Print table content.
            sum = 0
            additions = 0
            deletions = 0
            for key, value in new.items():
                # Processing too long name.
                key = shorten(key, 20, front=True)

                # Set color.
                lines_color = self.Level_Color[self.color_index(value["lines"])]

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

                print(
                    (
                        "| {:<21}"
                        "| {file_style}{:<11,}{reset} {file_change_style}{file_change:>5}{reset}"
                        "| {lines_style}{:<15,}{reset} {line_change_style}{line_change:>6}{reset}|"
                    ).format(
                        key,
                        value["files"],
                        value["lines"],
                        file_style=Fx.italic,
                        file_change_style=self.Symbol.get(files_symbol, ""),
                        file_change=files_change,
                        lines_style=lines_color,
                        line_change_style=self.Symbol.get(lines_symbol, ""),
                        line_change=lines_change,
                        reset=Fx.reset,
                    )
                )
                sum += value["lines"]
            print("-" * needed_width)
            # Print total and change graph.
            print(" Total: {}".format(sum))
            if additions > 0 or deletions > 0:
                print(" Altered: ", end="")
                print(
                    "{}{}".format(self.Symbol["+"], "+" * ceil(additions / 10)),
                    end="",
                )
                print(
                    "{}{}{}".format(
                        self.Symbol["-"], "-" * ceil(deletions / 10), Fx.reset
                    )
                )

    def count_and_format_print(self, if_save=True, show_invalid=False):
        result, invalid_list = self.count(self.count_path, self.use_ignore)
        old_result = self.load_recorded_result(self.count_path)
        # diff print.
        self.format_print(result, old_result)
        if if_save:
            self.save_result(result, self.count_path)
        if (
            show_invalid
            and invalid_list
            and confirm("Wether print invalid file list?[y/n]", default=False)
        ):
            print(invalid_list)
