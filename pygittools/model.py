# yapf: disable
class File:
    """Model class of git file."""

    def __init__(self,
        name, display_str, short_status,
        has_staged_change, has_unstaged_change,
        tracked, deleted, added,
        has_merged_conflicts,
        has_inline_merged_conflicts,
    ):
        """
        Args:
            name (str): File path relative to Git.
            display_str (str): Display string, may has color.
            short_status ():
            has_staged_change (bool): file wether has staged change.
            has_unstaged_change (bool): file wether has unstaged change.
            tracked (bool): Is the file on the tracking tree.
            deleted (bool): file wether deleted.
            added (bool): file wether added.
            has_merged_conflicts (bool): file wether has merged conflict.
            has_inline_merged_conflicts (bool): file wether has inline merged conflict.
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
