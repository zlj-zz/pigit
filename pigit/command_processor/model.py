# -*- coding:utf-8 -*-

"""This file save some model class of git info class."""

# flake8: noqa
class File:
    """Model class of git file."""

    def __init__(
        self,
        name: str,
        display_str: str,
        short_status: str,
        has_staged_change: bool,
        has_unstaged_change: bool,
        tracked: bool,
        deleted: bool,
        added: bool,
        has_merged_conflicts: bool,
        has_inline_merged_conflicts: bool,
    ):
        """
        Args:
            name (str): File path relative to Git.
            display_str (str): Display string, may has color.
            short_status (str): status string, like: 'MM'
            has_staged_change (bool): file whether has staged change.
            has_unstaged_change (bool): file whether has unstaged change.
            tracked (bool): Is the file on the tracking tree.
            deleted (bool): file whether deleted.
            added (bool): file whether added.
            has_merged_conflicts (bool): file whether has merged conflict.
            has_inline_merged_conflicts (bool): file whether has inline merged conflict.
        """

        self.name = name
        self.display_str = display_str
        self.short_status = short_status
        self.has_staged_change = has_staged_change
        self.has_unstaged_change = has_unstaged_change
        self.tracked = tracked
        self.deleted = deleted
        self.added = added
        self.has_merged_conflicts = has_merged_conflicts
        self.has_inline_merged_conflicts = has_inline_merged_conflicts
