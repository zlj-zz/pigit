# -*- coding:utf-8 -*-

"""This file save some model class of git info class."""

from typing import List
from dataclasses import dataclass

# flake8: noqa
@dataclass
class File:
    """Model class of git file."""

    # File path relative to Git.
    name: str
    # Display string, may has color.
    display_str: str

    # status string, like: 'MM'
    short_status: str

    # file whether has staged change.
    has_staged_change: bool

    # file whether has unstaged change.
    has_unstaged_change: bool

    # Is the file on the tracking tree.
    tracked: bool

    # file whether deleted.
    deleted: bool

    # file whether added.
    added: bool

    # file whether has merged conflict.
    has_merged_conflicts: bool

    # file whether has inline merged conflict.
    has_inline_merged_conflicts: bool

    def get_file_str(self) -> str:
        """Get the right file path str."""
        file_name = self.name

        if "->" in file_name:
            file_name = file_name.split("->")[-1].strip()

        return file_name

@dataclass
class Commit:
    """Model class of a git commit."""

    # The commit sha value.
    sha: str

    # The commit simple msg.
    msg: str

    # The author of the commit.
    author: str

    # The created time of the commit.
    unix_timestamp: int

    # The commit status, 'pushed' or 'unpushed'.
    status: str

    # The commit detail msg.
    extra_info: str

    # Tag list of the commit.
    tag: List

    action: str = ""

    def is_pushed(self) -> bool:
        return self.status == "pushed"


@dataclass
class Branch:
    """Model class of git branch."""

    # The branch name.
    name: str

    # The ahead time ou upstream, default '?'.
    ahead: str

    # The behind time ou upstream, default '?'.
    behind: str

    # This should be `True` if the branch is head.
    is_head: bool

    # The branch up-stream name. Default is "".
    upstream_name: str = ""
