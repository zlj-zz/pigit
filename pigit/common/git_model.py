# -*- coding:utf-8 -*-

"""This file save some model class of git info class."""

from dataclasses import dataclass

# flake8: noqa
# yapf: disable
@dataclass
class File:
    """Model class of git file."""

    name: str                         # File path relative to Git.
    display_str: str                  # Display string, may has color.
    short_status: str                 # status string, like: 'MM'
    has_staged_change: bool           # file whether has staged change.
    has_unstaged_change: bool         # file whether has unstaged change.
    tracked: bool                     # Is the file on the tracking tree.
    deleted: bool                     # file whether deleted.
    added: bool                       # file whether added.
    has_merged_conflicts: bool        # file whether has merged conflict.
    has_inline_merged_conflicts: bool # file whether has inline merged conflict.


@dataclass
class Commit:
    """Model class of git commit info."""

    sha: str
    msg: str
    author: str
    unix_timestamp: int
    status: str
    extra_info: str
    tag: list
    action: str = ""

    def is_pushed(self):
        return self.status == "pushed"


@dataclass
class Branch:
    name: str
    pushables: str
    pullables: str
    is_head: bool
    upstream_name: str = ""
