"""
Module: pigit/app_inspector.py
Description: Frozen selection snapshot sheet (top edge).
Author: Zev
Date: 2026-04-23
"""

from __future__ import annotations

from pigit.termui import bind_action, Component, dismiss_sheet, palette, Segment, Surface
from pigit.termui.widgets.line_text_browser import LineTextBrowser
from pigit.termui.widgets.sheet import Sheet

from .app_theme import THEME
from .app_types import (
    BranchSnapshot,
    CommitSnapshot,
    FileSnapshot,
    InspectorSnapshot,
    StashSnapshot,
)

_LABEL_WIDTH = 8


class InspectorSheet(Component):
    """Read-only snapshot of the selection; keys stay on this sheet."""

    keymap_namespace = "inspector"

    def __init__(self, rows: list[list[Segment]], **kwargs) -> None:
        super().__init__(**kwargs)
        self._browser = LineTextBrowser(content=rows, bg=None)
        self._browser.parent = self

    @property
    def focus_child(self) -> Component | None:
        return self._browser

    @staticmethod
    def format(snapshot: InspectorSnapshot) -> list[list[Segment]]:
        """Turn a snapshot into title + labeled body rows."""
        match snapshot:
            case FileSnapshot():
                return _format_file(snapshot)
            case BranchSnapshot():
                return _format_branch(snapshot)
            case CommitSnapshot():
                return _format_commit(snapshot)
            case StashSnapshot():
                return _format_stash(snapshot)

    @staticmethod
    def sheet_height(rows: list, term_h: int, *, border: int = 1) -> int:
        """Clamp sheet height to ``[3, term_h // 2]`` including border."""
        return Sheet.clamp_height(rows, term_h, border=border)

    def resize(self, size: tuple[int, int]) -> None:
        super().resize(size)
        self._browser.resize(size)

    def _render_surface(self, surface: Surface) -> None:
        self._browser._render_surface(surface)

    @bind_action("next", "j", "down", desc="Scroll down")
    def scroll_down(self) -> None:
        self._browser.scroll_down(1)

    @bind_action("previous", "k", "up", desc="Scroll up")
    def scroll_up(self) -> None:
        self._browser.scroll_up(1)

    @bind_action("close", "esc", "I", desc="Close")
    def close(self) -> None:
        dismiss_sheet()


def _title(kind: str, identity: str) -> list[Segment]:
    return [
        Segment(
            "Inspector",
            fg=THEME.fg_panel_title,
            style_flags=palette.STYLE_BOLD,
        ),
        Segment(" · ", fg=THEME.fg_muted),
        Segment(kind, fg=THEME.fg_info),
        Segment(" · ", fg=THEME.fg_muted),
        Segment(identity, fg=THEME.fg_primary),
    ]


def _labeled(label: str, values: list[Segment]) -> list[Segment]:
    prefix = f"{label:<{_LABEL_WIDTH}}" if len(label) <= _LABEL_WIDTH else f"{label} "
    return [Segment(prefix, fg=THEME.fg_muted), *values]


def _plain(text: str, fg: tuple[int, int, int] = THEME.fg_primary) -> list[Segment]:
    return [Segment(text, fg=fg)]


def _last_value(last: str) -> list[Segment]:
    sha, sep, rest = last.partition(" ")
    segs = [Segment(sha, fg=THEME.fg_dim)]
    if sep:
        segs.append(Segment(sep + rest, fg=THEME.fg_primary))
    return segs


def _numstat_rows(
    files: list[tuple[str, int, int]], total_add: int, total_del: int
) -> list[list[Segment]]:
    rows = [
        _labeled(
            "changes",
            [
                Segment(f"+{total_add}", fg=THEME.fg_success),
                Segment(" ", fg=THEME.fg_muted),
                Segment(f"-{total_del}", fg=THEME.fg_danger),
            ],
        )
    ]
    for name, add, delete in files:
        rows.append(
            [
                Segment("  ", fg=THEME.fg_dim),
                Segment(name, fg=THEME.fg_primary),
                Segment(" ", fg=THEME.fg_muted),
                Segment(f"+{add}", fg=THEME.fg_success),
                Segment(" ", fg=THEME.fg_muted),
                Segment(f"-{delete}", fg=THEME.fg_danger),
            ]
        )
    return rows


def _format_file(data: FileSnapshot) -> list[list[Segment]]:
    rows = [
        _title("file", data.identity),
        _labeled("path", _plain(data.path)),
        _labeled("blobs", _plain(data.blobs)),
    ]
    if data.stages:
        rows.append(_labeled("stages", _plain(data.stages)))
    if data.size != "?":
        rows.append(_labeled("size", _plain(data.size)))
    if data.mode != "?":
        rows.append(_labeled("mode", _plain(data.mode)))
    if data.last:
        rows.append(_labeled("last", _last_value(data.last)))
    return rows


def _format_branch(data: BranchSnapshot) -> list[list[Segment]]:
    if data.contained is None:
        contained, contained_fg = "?", THEME.fg_muted
    else:
        contained = "yes" if data.contained else "no"
        contained_fg = THEME.fg_success if data.contained else THEME.fg_danger
    current_fg = THEME.fg_success if data.current == "yes" else THEME.fg_primary
    rows = [
        _title("branch", data.identity),
        _labeled("tip", _plain(data.tip, THEME.fg_dim)),
    ]
    if data.created:
        rows.append(_labeled("created", _plain(data.created)))
    rows.append(_labeled("current", _plain(data.current, current_fg)))
    rows.append(_labeled("upstream", _plain(data.upstream)))
    rows.append(_labeled("ahead", _plain(data.ahead)))
    rows.append(_labeled("behind", _plain(data.behind)))
    if data.recent_msg != "?":
        rows.append(_labeled("recent", _plain(data.recent_msg)))
    if data.recent_author != "?":
        rows.append(_labeled("by", _plain(data.recent_author)))
    rows.append(_labeled("contained", _plain(contained, contained_fg)))
    return rows


def _format_commit(data: CommitSnapshot) -> list[list[Segment]]:
    parents = " ".join(data.parents) if data.parents else "(root)"
    status_fg = THEME.fg_success if data.status == "pushed" else THEME.fg_warning
    rows = [
        _title("commit", data.identity),
        _labeled("msg", _plain(data.msg)),
        _labeled("author", _plain(data.author)),
        _labeled("when", _plain(data.when)),
        _labeled("status", _plain(data.status, status_fg)),
        _labeled("tags", _plain(data.tags)),
        _labeled("sha", _plain(data.sha, THEME.fg_dim)),
        _labeled("parents", _plain(parents)),
    ]
    rows.extend(_numstat_rows(data.files, data.total_add, data.total_del))
    return rows


def _format_stash(data: StashSnapshot) -> list[list[Segment]]:
    rows = [_title("stash", data.identity)]
    if data.author:
        rows.append(_labeled("author", _plain(data.author)))
    if data.when:
        rows.append(_labeled("when", _plain(data.when)))
    if data.parents:
        rows.append(_labeled("parents", _plain(" ".join(data.parents))))
    rows.extend(_numstat_rows(data.files, data.total_add, data.total_del))
    return rows
