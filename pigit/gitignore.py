# -*- coding:utf-8 -*-

from __future__ import print_function
import os
import re

from .compat import urlopen
from .utils import confirm
from .common import Fx, Emotion


class GitignoreGenetor(object):
    """Generate gitignore template.

    Attributes:
        Genres (dict): supported type.

    Raises:
        SystemExit: Can't get template.
        SystemExit: No name.
    """

    # Supported type. https://github.com/github/gitignore
    Supported_Types = {
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

    def __init__(self, timeout=60):
        super(GitignoreGenetor, self).__init__()

        self.timeout = timeout

    def parse_gitignore_page(self, content):
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

    def get_ignore_from_url(self, url):
        """Crawl gitignore template.

        Args:
            url (str): gitignore template url.

        Raises:
            SystemExit: Failed to get web page.

        Returns:
            (str): html string.
        """

        try:
            handle = urlopen(url, timeout=self.timeout)
        except Exception:
            # Exit once an error occurs.
            print("Failed to get content and will exit.")
            raise SystemExit(0)

        content = handle.read().decode("utf-8")

        return content

    def create_gitignore(self, genre, dir_path):
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
                "Supported type: %s.  Case insensitive."
                % " ".join(self.Supported_Types.keys())
            )
            raise SystemExit(0)

        ignore_path = dir_path + "/.gitignore"
        whether_write = True
        if os.path.exists(ignore_path):
            print(
                "`.gitignore` existed, overwrite this file? (default: y) [y/n]:",
                end="",
            )
            whether_write = confirm()
        if whether_write:
            base_url = "https://github.com/github/gitignore/blob/master/%s.gitignore"

            target_url = base_url % name
            print(
                "Will get ignore file content from %s"
                % (Fx.italic + Fx.underline + target_url + Fx.reset)
            )
            content = self.get_ignore_from_url(target_url)
            ignore_content = self.parse_gitignore_page(content)

            print("Got content, trying to write ... ")
            try:
                with open(ignore_path, "w") as fd:
                    fd.write(ignore_content)
                print(
                    "Write gitignore file successful. {0}".format(Emotion.Icon_Smiler)
                )
            except Exception:
                print("Write gitignore file failed.")
                print("You can replace it with the following:")
                print("#" * 60)
                print(ignore_content)
