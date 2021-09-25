# -*- coding:utf-8 -*-

import os
import re
import logging
from typing import Optional
from urllib.request import urlopen

from .utils import confirm
from .common import Fx, Emotion

Log = logging.getLogger(__name__)


class GitignoreGenetor(object):
    """Generate gitignore template.

    Attributes:
        Genres (dict): supported type.

    Raises:
        SystemExit: Can't get template.
        SystemExit: No name.
    """

    # Supported type. https://github.com/github/gitignore
    Supported_Types: dict[str, str] = {
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

    def __init__(self, timeout=60) -> None:
        super(GitignoreGenetor, self).__init__()

        self.timeout = timeout

    def parse_gitignore_page(self, content: str) -> str:
        """Parse html for getting gitignore content.

        Args:
            content (str): template page html.

        Returns:
            (str): gitignore template content.
        """

        # findall table tag, should only one.
        text = re.findall(r"(<table.*?>.*?<\/table>)", content, re.S)
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
            Log.error(str(e) + str(e.__traceback__))
            # Exit once an error occurs.
            return None
        else:
            content = handle.read().decode("utf-8")
            return content

    def launch(self, genre: str, dir_path: str) -> None:
        """Try to create gitignore template file.

        Args:
            genre (str): template type, like: 'python'.
            dir_path (str): .gitignore file save path.
        """

        # Process and check the type, and exit in case of any accident.
        name = self.Supported_Types.get(genre.lower(), None)
        if name is None:
            print("Unsupported type: %s" % genre)
            print(
                "Supported type: [{}]. Case insensitive.".format(
                    " ".join(self.Supported_Types.keys())
                )
            )
            return None

        ignore_path = dir_path + "/.gitignore"
        whether_write = True

        # Adjust `.gitignore` whether exist.
        if os.path.exists(ignore_path):
            whether_write = confirm(
                "`.gitignore` existed, overwrite this file? (default: y) [y/n]:"
            )

        if whether_write:
            base_url = "https://github.com/github/gitignore/blob/master/%s.gitignore"
            target_url = base_url % name

            print(
                "Will get ignore file content from %s"
                % (Fx.italic + Fx.underline + target_url + Fx.reset)
            )
            content = self.get_html_from_url(target_url)
            if not content:
                print("Failed to get content and will exit.")
                return None

            ignore_content = self.parse_gitignore_page(content)

            print("Got content, trying to write ... ")
            try:
                with open(ignore_path, "w") as fd:
                    fd.write(ignore_content)
            except Exception as e:
                Log.error(str(e) + str(e.__traceback__))
                print("Write gitignore file failed.")
                print("You can copy it with the following:")
                print("#" * 60)
                print(ignore_content)
            else:
                print(
                    "Write gitignore file successful. {0}".format(Emotion.Icon_Smiler)
                )
