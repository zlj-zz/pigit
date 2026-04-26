# -*- coding: utf-8 -*-
"""
Module: pigit/cmdparse/completion/widgets.py
Description: Shell widget code for pigit cmd picker integration.
Author: Zev
Date: 2026-04-15
"""


def _widget_body(shell_set_cmd: str) -> str:
    """Generate the common widget body for a given shell.

    Args:
        shell_set_cmd: Shell-specific command to set the command line buffer.

    Returns:
        Widget source code string.
    """
    return f"""\
    local tmpfile
    tmpfile=$(mktemp)
    PIGIT_WIDGET_OUTPUT="$tmpfile" pigit cmd --pick-print < /dev/tty > /dev/tty 2>&1
    if [[ -s "$tmpfile" ]]; then
        {shell_set_cmd}
    fi
    rm -f "$tmpfile"
"""


_BASH_SET = 'READLINE_LINE="$(<"$tmpfile")"\n    READLINE_POINT=${#READLINE_LINE}'
_ZSH_SET = 'BUFFER="$(<"$tmpfile")"\n    CURSOR=${#BUFFER}'

BASH_WIDGET = f"""\
# PIGIT cmd picker widget (Ctrl+G)
_pigit_cmd_widget() {{
{_widget_body(_BASH_SET)}
}}
bind -x '"\\C-g": _pigit_cmd_widget'
"""

ZSH_WIDGET = f"""\
# PIGIT cmd picker widget (Ctrl+G)
_pigit_cmd_widget() {{
{_widget_body(_ZSH_SET)}
    zle redisplay
}}
zle -N _pigit_cmd_widget
bindkey '^G' _pigit_cmd_widget
"""

FISH_WIDGET = """\
# PIGIT cmd picker widget (Ctrl+G)
function __pigit_cmd_widget
    set -l tmpfile (mktemp)
    PIGIT_WIDGET_OUTPUT="$tmpfile" pigit cmd --pick-print < /dev/tty > /dev/tty 2>&1
    if test -s "$tmpfile"
        commandline -r (cat "$tmpfile")
    end
    rm -f "$tmpfile"
end
bind \\cg __pigit_cmd_widget
"""

WIDGETS = {
    "bash": BASH_WIDGET,
    "zsh": ZSH_WIDGET,
    "fish": FISH_WIDGET,
}
