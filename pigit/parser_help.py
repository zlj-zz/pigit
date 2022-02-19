import argparse
from shutil import get_terminal_size

from .common import Color
from .config import Config


class CustomHelpFormatter(argparse.HelpFormatter):
    """Formatter for generating usage messages and argument help strings.

    This class inherits `argparse.HelpFormatter` and rewrites some methods
    to complete customization.
    """

    def __init__(
        self, prog, indent_increment=2, max_help_position=24, width=90, colors=None
    ):
        width = Config.help_max_line_width
        max_width, _ = get_terminal_size()

        width = width if width < max_width else max_width - 2
        super(CustomHelpFormatter, self).__init__(
            prog, indent_increment, max_help_position, width
        )
        if not colors or not isinstance(colors, list):
            colors = {
                "red": Color.fg("#FF6347"),  # Tomato
                "green": Color.fg("#98FB98"),  # PaleGreen
                "yellow": Color.fg("#EBCB8C"),  # Yellow
                "blue": Color.fg("#87CEFA"),  # SkyBlue
                # Color.fg("#FFC0CB"),  # Pink
            }
        self.colors = colors
        self.color_len = len(colors)
        self._old_color = None

    def _format_action(self, action):
        # determine the required width and the entry label
        help_position = min(self._action_max_length + 2, self._max_help_position)
        help_width = max(self._width - help_position, 11)
        action_width = help_position - self._current_indent - 2
        action_header = self._format_action_invocation(action)

        # no help; start on same line and add a final newline
        if not action.help:
            tup = self._current_indent, "", action_header
            action_header = "%*s%s\n" % tup

        # short action name; start on the same line and pad two spaces
        elif len(action_header) <= action_width:
            tup = self._current_indent, "", action_width, action_header
            action_header = "%*s%-*s  " % tup
            indent_first = 0

        # long action name; start on the next line
        else:
            tup = self._current_indent, "", action_header
            action_header = "%*s%s\n" % tup
            indent_first = help_position

        # collect the pieces of the action help
        # @Overwrite
        if Config.help_use_color:
            _color = self.colors["green"]
        else:
            _color = ""
        parts = [_color + action_header + "\033[0m"]

        # if there was help for the action, add lines of help text
        if action.help:
            help_text = self._expand_help(action)
            help_lines = self._split_lines(help_text, help_width)
            parts.append("%*s%s\n" % (indent_first, "", help_lines[0]))
            for line in help_lines[1:]:
                parts.append("%*s%s\n" % (help_position, "", line))

        # or add a newline if the description doesn't end with one
        elif not action_header.endswith("\n"):
            parts.append("\n")

        # if there are any sub-actions, add their help as well
        for subaction in self._iter_indented_subactions(action):
            parts.append(self._format_action(subaction))

        # return a single string
        return self._join_parts(parts)

    def _fill_text(self, text, width, indent):
        try:
            return "".join(indent + line for line in text.splitlines(keepends=True))
        except TypeError:
            return "".join(indent + line for line in text.splitlines())

    def _get_help_string(self, action):
        help = action.help
        if "%(default)" not in action.help:
            if action.default is not argparse.SUPPRESS:
                defaulting_nargs = [argparse.OPTIONAL, argparse.ZERO_OR_MORE]
                if action.option_strings or action.nargs in defaulting_nargs:
                    # help += " (default: %(default)s)"
                    pass
        return help
