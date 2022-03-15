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

    # This should be `True` if the branch can be pushing.
    pushables: str

    # This should be `True` if the branch can be pulling.
    pullables: str

    # This should be `True` if the branch is head.
    is_head: bool

    # The branch up-stream name. Default is "".
    upstream_name: str = ""
