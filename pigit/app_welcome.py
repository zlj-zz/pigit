"""
Module: pigit/app_welcome.py
Description: First-run Welcome Sheet content and keyboard handling.
Author: Zev
Date: 2026-08-28
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import replace
from typing import TYPE_CHECKING, Any

from pigit.termui import (
    bind_action,
    Component,
    dismiss_sheet,
    palette,
    Segment,
    Surface,
)
from pigit.termui.bindings import ExecutableBinding, merge_footer_pairs
from pigit.termui.tty_io import terminal_size
from pigit.termui.widgets import (
    Sheet,
    TextBrowser,
    block_inset_for,
    format_binding_group_rows,
    wrap_text,
)

from .app_theme import THEME
from .config_data import AppConfig
from .const import __url__
from .welcome_state import load_welcome_seen

if TYPE_CHECKING:
    from .app import PigitApplication

# Content rows + edge rule row + one line margin for auto-show gate.
_WELCOME_EDGE_MARGIN = 2
# Welcome may use up to two-thirds of the terminal height.
WELCOME_SHEET_MAX_FRACTION = 2 / 3
# Keep copy off the sheet border on wide terminals.
_WELCOME_INSET_MIN = 4
_WELCOME_INNER_WIDTH = 72
_WELCOME_INTRO_WIDTH = 72

_INTRO_BODY = (
    "Pigit is a keyboard-driven Git TUI for everyday work in the terminal: "
    "stage, commit, branch, and browse history without memorizing long git "
    "commands or leaving the shell. Beyond the four-panel UI, you get "
    "hunk-level staging, session undo (u/U), remappable keybindings, "
    "multi-repo management (pigit repo), and CLI short-commands (pigit cmd) "
    "— one install for repo work and git ergonomics."
)

_PANEL_ACTIONS = (
    "universal.goto_status",
    "universal.goto_stash",
    "universal.goto_branch",
    "universal.goto_commit",
)

_PANEL_WELCOME_DESC: dict[str, str] = {
    "universal.goto_status": "Status — stage, commit, discard working tree changes",
    "universal.goto_stash": "Stash — stash stack (column with Status)",
    "universal.goto_branch": "Branch — checkout, merge, create branches",
    "universal.goto_commit": "Commit — history, graph, cherry-pick",
}

_WELCOME_GLOBAL_ACTIONS = (
    "universal.help",
    "universal.palette",
    "universal.next_panel",
    "universal.prev_panel",
    "universal.quit",
    "universal.undo",
)

_WELCOME_GLOBAL_DESC_OVERRIDES: dict[str, str] = {
    "universal.help": "Full help — j/k navigate, Enter to run actions",
}


def _welcome_banner_rows() -> list[list[Segment]]:
    """Compact git-graph ASCII mark above the welcome copy."""
    dim = THEME.fg_dim
    accent = THEME.fg_accent
    title = THEME.fg_panel_title
    bold = palette.STYLE_BOLD

    def node(text: str) -> Segment:
        return Segment(text, fg=accent, style_flags=bold)

    def wire(text: str) -> Segment:
        return Segment(text, fg=dim)

    def wordmark() -> list[Segment]:
        return [
            wire("    "),
            Segment(" ·  ", fg=dim),
            Segment("P i g i t", fg=title, style_flags=bold),
            Segment(" ·", fg=dim),
        ]

    return [
        [
            wire("      "),
            node("o"),
            wire("──"),
            node("o"),
            wire("──"),
            node("●"),
        ],
        [
            wire("     ╱──"),
            node("o"),
            *wordmark(),
        ],
    ]


def _project_home_url() -> str:
    """Public GitHub URL for display (no ``.git`` suffix)."""
    if __url__.endswith(".git"):
        return __url__[:-4]
    return __url__


def _welcome_intro_rows() -> list[list[Segment]]:
    """Product intro between the banner and the binding cheat sheet."""
    muted = THEME.fg_muted
    accent = THEME.fg_accent
    info = THEME.fg_info
    bold = palette.STYLE_BOLD

    rows: list[list[Segment]] = [
        [
            Segment(
                "Stay in the terminal. Ship the commit.",
                fg=accent,
                style_flags=bold,
            ),
        ],
        [],
    ]
    for line in wrap_text(_INTRO_BODY, _WELCOME_INTRO_WIDTH):
        rows.append([Segment(line, fg=muted)])
    rows.extend(
        [
            [],
            [
                Segment("The keys below are a quick start; ", fg=muted),
                Segment("?", fg=accent, style_flags=bold),
                Segment(
                    " opens the full interactive help panel.",
                    fg=muted,
                ),
            ],
            [Segment(_project_home_url(), fg=info)],
        ]
    )
    return rows


def _welcome_footer_row() -> list[Segment]:
    """Point users at full Help and manual reopen."""
    muted = THEME.fg_muted
    accent = THEME.fg_accent
    dot = Segment("  ·  ", fg=muted)
    return [
        Segment("Press ", fg=muted),
        Segment("?", fg=accent, style_flags=palette.STYLE_BOLD),
        Segment(" for the full key list", fg=muted),
        dot,
        Segment("Help → Show welcome", fg=muted),
        Segment(" to reopen", fg=muted),
    ]


def _executable_by_action(
    rows: Sequence[ExecutableBinding],
) -> dict[str, ExecutableBinding]:
    return {row.action: row for row in rows}


def _with_desc(row: ExecutableBinding, desc: str) -> ExecutableBinding:
    return replace(row, desc=desc)


def get_welcome_groups(app: Any) -> list[tuple[str, list[ExecutableBinding]]]:
    """Curated Help-shaped groups projected from app executable bindings."""
    by_action = _executable_by_action(app.get_executable_bindings())

    panels: list[ExecutableBinding] = []
    for action in _PANEL_ACTIONS:
        row = by_action.get(action)
        if row is None:
            continue
        panels.append(_with_desc(row, _PANEL_WELCOME_DESC[action]))

    global_rows: list[ExecutableBinding] = []
    for action in _WELCOME_GLOBAL_ACTIONS:
        row = by_action.get(action)
        if row is None:
            continue
        desc = _WELCOME_GLOBAL_DESC_OVERRIDES.get(action, row.desc)
        global_rows.append(_with_desc(row, desc))

    groups: list[tuple[str, list[ExecutableBinding]]] = []
    if panels:
        groups.append(("Panels", panels))
    if global_rows:
        groups.append(("Global", global_rows))
    return groups


def build_welcome_content(app: PigitApplication) -> list[list[Segment]]:
    """Build Welcome copy: banner, intro, Help-formatted bindings, footer tip."""
    groups = get_welcome_groups(app)
    body = format_binding_group_rows(
        groups,
        inner_width=_WELCOME_INNER_WIDTH,
        key_fg=THEME.fg_accent,
        desc_fg=THEME.fg_muted,
        show_cursor=False,
    )
    return [
        [],
        *_welcome_banner_rows(),
        [],
        *_welcome_intro_rows(),
        [],
        *body,
        [],
        _welcome_footer_row(),
    ]


def welcome_min_terminal_rows(content_rows: int) -> int:
    """Minimum terminal height required to auto-show Welcome."""
    return content_rows + _WELCOME_EDGE_MARGIN


def should_auto_show_welcome(
    config: AppConfig,
    host: Component | None,
    *,
    min_terminal_rows: int = 10,
    content_rows: int,
) -> bool:
    """Single gate for automatic Welcome on first run.

    Args:
        config: Application configuration.
        host: Overlay host (:class:`~pigit.termui.root.ComponentRoot`).
        min_terminal_rows: Application ``min_terminal_size`` row count.
        content_rows: Rendered Welcome row count.

    Returns:
        True when Welcome should open automatically once.
    """
    if not config.show_welcome:
        return False
    if load_welcome_seen():
        return False
    if host is None:
        return False
    stolen = getattr(host, "is_presentation_stolen", None)
    if callable(stolen) and stolen():
        return False
    _cols, rows = terminal_size()
    min_rows = max(welcome_min_terminal_rows(content_rows), min_terminal_rows)
    if rows < min_rows:
        return False
    return True


class WelcomeSheet(Component):
    """Read-only onboarding sheet; keys stay on this component."""

    keymap_namespace = "welcome"

    def __init__(
        self,
        *,
        rows: list[list[Segment]],
        on_dismiss: Callable[[], None],
    ) -> None:
        super().__init__()
        self._on_dismiss = on_dismiss
        self._rows = rows
        self._browser = TextBrowser(
            content=self._rows,
            bg=None,
            content_inset=block_inset_for("center", min_inset=_WELCOME_INSET_MIN),
            content_valign="center",
        )
        self._browser.parent = self

    @property
    def focus_child(self) -> Component | None:
        return self._browser

    def preferred_sheet_height(self, term_h: int) -> int:
        """Fit content plus facing-edge rule (up to two-thirds of terminal)."""
        return Sheet.clamp_height(
            self._rows,
            term_h,
            border=1,
            max_fraction=WELCOME_SHEET_MAX_FRACTION,
        )

    def get_footer_entries(self) -> list[tuple[str, str]]:
        """Footer hints while Welcome owns the SHEET layer."""
        viewport = self._size[1] if self._size[1] > 0 else self._browser.viewport_rows
        if len(self._rows) <= viewport:
            return merge_footer_pairs(
                [
                    ("esc", "Close"),
                    ("enter", "Close"),
                ]
            )
        return merge_footer_pairs(
            [
                ("esc", "Close"),
                ("enter", "Close"),
                ("j", "Navigate"),
                ("k", "Navigate"),
                ("up", "Navigate"),
                ("down", "Navigate"),
            ]
        )

    def resize(self, size: tuple[int, int]) -> None:
        super().resize(size)
        self._browser.resize(size)

    def paint(self, surface: Surface) -> None:
        self._browser.paint(surface)

    @bind_action("next", "j", "down", desc="Scroll down")
    def scroll_down(self) -> None:
        self._browser.scroll_down(1)

    @bind_action("previous", "k", "up", desc="Scroll up")
    def scroll_up(self) -> None:
        self._browser.scroll_up(1)

    @bind_action("close", "esc", "enter", desc="Close welcome", tip="Close")
    def close(self) -> None:
        """Dismiss the sheet and run the app-provided callback."""
        self._on_dismiss()
        dismiss_sheet()
