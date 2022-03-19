# -*- coding:utf-8 -*-

from typing import Dict, Optional
import os, re
import logging
from urllib.request import urlopen

from .common.utils import confirm, traceback_info
from .render import get_console


Log = logging.getLogger(__name__)


# Supported type. https://github.com/github/gitignore
SUPPORTED_GITIGNORE_TYPES: Dict[str, str] = {
    "android": "Android",
    "c++": "C++",
    "cpp": "C++",
    "c": "C",
    "dart": "Dart",
    "elisp": "Elisp",
    "gitbook": "GitBook",
    "go": "Go",
    "java": "Java",
    "kotlin": "Java",
    "lua": "Lua",
    "maven": "Maven",
    "node": "Node",
    "python": "Python",
    "qt": "Qt",
    "r": "R",
    "ros": "ROS",
    "ruby": "Ruby",
    "rust": "Rust",
    "sass": "Sass",
    "swift": "Swift",
    "unity": "Unity",
}


class GitignoreGenetor(object):
    """Generate gitignore template.

    Raises:
        SystemExit: Can't get template.
        SystemExit: No name.
    """

    def __init__(self, timeout: int = 60) -> None:
        super(GitignoreGenetor, self).__init__()

        self.timeout = timeout

    def parse_gitignore_page(self, html: str) -> str:
        """Parse html for getting gitignore content.

        Args:
            content (str): template page html.

        Returns:
            (str): gitignore template content.
        """

        # findall table tag, should only one.
        text = re.findall(r"(<table.*?>.*?<\/table>)", html, re.S)
        if not text:
            return ""

        # remove all html tag.
        content_re = re.compile(r"<\/?\w+.*?>", re.S)
        res = content_re.sub("", text[0])
        # replace multi empty line to one line.
        res = re.sub(r"(\n[^\S\r\n]+)+", "\n", res)
        return res

    def get_html_from_url(self, url: str) -> Optional[str]:
        """Crawl gitignore template.

        Args:
            url (str): gitignore template url.

        Returns:
            (str): html string.
        """

        try:
            handle = urlopen(url, timeout=self.timeout)
        except Exception as e:
            Log.error(traceback_info())
            # Exit once an error occurs.
            return None
        else:
            return handle.read().decode("utf-8")

    def out_ignore_content(self, content: str) -> None:
        print("You can copy it with the following:")
        print("#" * 80)
        print(content)
        print("#" * 80)

    def launch(
        self,
        ignore_type: str,
        dir_path: str,
        writting: bool = True,
        file_name: str = ".gitignore",
    ) -> bool:
        """Try to create gitignore template file.

        Args:
            ignore_type (str): the type that want to generate.
            dir_path (str): the path for saving.
            writing (bool, optional): whether write to a file. Defaults to True.
            file_name (str, optional): the name of generate file. Defaults to ".gitignore".

        Returns:
            bool: whether run it successful.
        """

        name = SUPPORTED_GITIGNORE_TYPES.get(ignore_type.lower(), None)
        ignore_path = os.path.join(dir_path, file_name)

        # Process and check the type, and exit in case of any accident.
        if name is None:
            print(f"Unsupported type: {ignore_type}")
            print(
                f'Supported type: [{" ".join(SUPPORTED_GITIGNORE_TYPES)}]. Case insensitive.'
            )

            return False

        # Adjust `.gitignore` whether exist.
        if writting and os.path.exists(ignore_path):
            re_writing = confirm(
                f"The `{file_name}` existed, overwrite this file? (default: y) [y/n]:"
            )
            if not re_writing:
                print("Cancel generate gitignore file.")
                return False

        base_url = "https://github.com/github/gitignore/blob/main/%s.gitignore"
        target_url = base_url % name

        get_console().echo(
            f"Will get ignore file content from (i,u)`{target_url}`"
            # f"Will get ignore file content from {Fx.italic + Fx.underline + target_url + Fx.reset}"
        )

        content = self.get_html_from_url(target_url)
        if not content:
            print("Failed to get content and will exit.")
            return False

        ignore_content = self.parse_gitignore_page(content)

        if writting:
            print("Got content, trying to write ... ")
            try:
                with open(ignore_path, "w") as fd:
                    fd.write(ignore_content)
            except Exception:
                Log.error(traceback_info())
                self.out_ignore_content(ignore_content)

            else:
                get_console().echo("Write gitignore file successful. :smiler:")
        else:
            self.out_ignore_content(ignore_content)

        return True
