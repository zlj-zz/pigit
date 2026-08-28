"""
Module: pigit/app_keybindings.py
Description: Enumerate configurable keybindings and render the [app.keybindings] config template.
Author: Zev
Date: 2026-08-16
"""

from __future__ import annotations

import sys
from collections.abc import Sequence

from pigit.termui import Binding, collect_action_bindings
from pigit.termui.cli_output import get_console
from .app import PigitApplication
from .app_branch import BranchPanel
from .app_commit import CommitPanel
from .app_diff import DiffViewer
from .app_inspector import InspectorSheet
from .app_log_ref import LogRefSheet
from .app_rebase import RebasePanel
from .app_recent_actions import RecentActionsPanel
from .app_repo_switcher import RepoSwitcherSheet
from .app_stash import StashPanel
from .app_welcome import WelcomeSheet
from .app_status import StatusPanel

# The classes that declare a ``keymap_namespace``; the namespace itself is read
# from each class (single source) rather than duplicated here.
_KEYMAP_CLASSES: tuple[type, ...] = (
    PigitApplication,
    StatusPanel,
    StashPanel,
    BranchPanel,
    CommitPanel,
    DiffViewer,
    RebasePanel,
    RecentActionsPanel,
    RepoSwitcherSheet,
    LogRefSheet,
    InspectorSheet,
    WelcomeSheet,
)

_KEY_SYNTAX_HINT = (
    '# Key syntax: semantic keys ("c", "down", "ctrl c", " " for space).\n'
    "# Uncomment a line and change the key to remap an action."
)


def collect_all_action_bindings() -> list[tuple[str, Binding]]:
    """Enumerate every configurable action as ``(namespace, binding)`` pairs."""
    out: list[tuple[str, Binding]] = []
    for cls in _KEYMAP_CLASSES:
        namespace = cls.keymap_namespace
        out.extend((namespace, b) for b in collect_action_bindings(cls, namespace))
    return out


def warn_unmatched_keybindings(
    bindings: Sequence[tuple[str, Binding]],
    keybindings: dict[str, str | list[str]],
) -> None:
    """Warn (stderr) about ``[app.keybindings]`` keys that match no known action."""
    if not keybindings:
        return
    known = {binding.action for _, binding in bindings if binding.configurable}
    orphans = sorted(key for key in keybindings if key not in known)
    if not orphans:
        return
    console = get_console()
    print(console.render("@bold(@yellow(Config Warning))"), file=sys.stderr)
    print(
        "The following [app.keybindings] keys match no configurable action and are ignored:",
        file=sys.stderr,
    )
    for key in orphans:
        print(f"  - {key}", file=sys.stderr)


def render_keybindings_template(
    bindings: Sequence[tuple[str, Binding]],
    keybindings: dict[str, str | list[str]],
    *,
    include_defaults: bool = False,
) -> str:
    """Render the ``[app.keybindings]`` block.

    Overridden actions are emitted as active lines (preserved); non-overridden
    actions are emitted as commented defaults only when ``include_defaults`` is
    set. Returns ``""`` when there is nothing to render.
    """
    groups: dict[str, list[str]] = {}
    for namespace, binding in bindings:
        if not binding.configurable:
            continue
        overridden = binding.action in keybindings
        if not overridden and not include_defaults:
            continue
        short = binding.action[len(namespace) + 1 :]
        if overridden:
            line = f"{short} = {_toml_str(keybindings[binding.action])}"
            line += f"  # default: {_toml_str(binding.keys)}"
        else:
            desc = binding.desc
            if callable(desc):
                desc = short
            line = f"# {short} = {_toml_str(binding.keys)}"
            if desc:
                line += f"  # {desc}"
        groups.setdefault(namespace, []).append(line)

    if not groups:
        return ""

    lines = [_KEY_SYNTAX_HINT]
    for namespace, group_lines in groups.items():
        lines.append("")
        lines.append(f"[app.keybindings.{namespace}]")
        lines.extend(group_lines)
    return "\n" + "\n".join(lines) + "\n"


def _toml_str(keys: str | list[str] | tuple[str, ...]) -> str:
    """Render a semantic key (or sequence) as a TOML string or array."""
    values = [keys] if isinstance(keys, str) else list(keys)
    rendered = [_quote(k) for k in values]
    if len(rendered) == 1:
        return rendered[0]
    return "[" + ", ".join(rendered) + "]"


def _quote(key: str) -> str:
    escaped = key.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'
