"""
Module: pigit/app_diff.py
Description: DiffViewer with TrueColor diff rendering and heatmap column.
Author: Zev
Date: 2026-04-23
"""

from __future__ import annotations

import bisect
import dataclasses
import enum
import logging
import os
import re
import subprocess
import tempfile

from pigit.termui import (
    ActionEventType,
    AlertDialog,
    Component,
    SyntaxTokenizer,
    keys,
    palette,
    bind_keys,
    show_badge,
    show_toast,
)
from pigit.termui._text import plain
from pigit.termui.widgets import LineTextBrowser
from pigit.termui.wcwidth_table import truncate_by_width, wcswidth

from .app_theme import THEME

_logger = logging.getLogger(__name__)

_HUNK_HEADER_RE = re.compile(r"@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@")
_DIFF_GIT_RE = re.compile(r"^diff --git a/(.+) b/(.+)$")


@dataclasses.dataclass
class _DiffStateSnapshot:
    """Immutable snapshot of diff view state for later restoration."""

    content: list[str]
    diff_type: DiffType
    scroll_i: int
    come_from: Component | None


class DiffType(enum.Enum):
    UNSTAGED = "unstaged"
    STAGED = "staged"
    COMMIT = "commit"
    STASH = "stash"


@dataclasses.dataclass
class _Hunk:
    """A single diff hunk boundary."""

    start: int  # index into _content (includes @@ line)
    end: int  # index into _content (excludes next @@ or EOF)
    old_start: int
    old_count: int
    new_start: int
    new_count: int
    file_header_start: int  # index of 'diff --git' line for this file


class DiffViewer(LineTextBrowser):
    """Diff viewer with TrueColor background rendering, line numbers, and heatmap column."""

    _CACHE_MAX = 64
    LINE_NO_WIDTH = 5
    LINE_NO_STR_WIDTH = 4  # LINE_NO_WIDTH - 1
    DIFF_PREFIX_WIDTH = 1
    SCROLL_PAGE_SIZE = 5
    TAB_WIDTH = 8
    DENSITY_SHORT = 10
    DENSITY_MEDIUM = 30
    DENSITY_LONG = 60
    BORDER_ROWS = 2
    BORDER_COLS = 2

    @staticmethod
    def _is_file_header(line: str) -> bool:
        return line.startswith("--- ") or line.startswith("+++ ")

    @staticmethod
    def _is_add_line(line: str) -> bool:
        return line.startswith("+") and not line.startswith("+++")

    @staticmethod
    def _is_del_line(line: str) -> bool:
        return line.startswith("-") and not line.startswith("---")

    def _main_width(self, available: int) -> int:
        return available - self.LINE_NO_WIDTH - self.DIFF_PREFIX_WIDTH - 1

    def __init__(
        self,
        x: int = 1,
        y: int = 1,
        size: tuple[int, int] | None = None,
        id: str | None = None,
    ) -> None:
        super().__init__(x, y, size, [], id=id)
        # LineTextBrowser sets _max_line to full height; adjust for border rows
        if self._size[1] >= 3:
            self._max_line = self._size[1] - 2
        self._heatmap: list[str] = []
        self._heatmap_colors: list[tuple[int, int, int]] = []
        self._line_numbers: list[str] = []
        self.come_from: Component | None = None
        self.i_cache_key = ""
        self.i_cache: dict[str, int] = {}
        self._tokenizer = SyntaxTokenizer()
        self._line_langs: list[str] = []
        self._multiline_mask: list[str | None] = []
        # _render_tokens holds (text, fg_color, display_width) per token
        self._render_tokens: list[list[tuple[str, tuple[int, int, int], int]]] = []
        self._hunk_starts: list[int] = []
        self._hunk_mode = False
        self._hunk_index = 0
        self._hunks: list[_Hunk] = []
        self._repo_path = ""
        self._diff_type = DiffType.UNSTAGED
        self._alert_dialog = AlertDialog(on_result=lambda _: None)

        # File history state
        self._file_history_mode = False
        self._file_history_path: str = ""
        self._file_history_commits: list[tuple[str, str]] = []
        self._file_history_index: int = 0
        self._file_history_cache: dict[str, list[str]] = {}
        self._saved_diff_state: _DiffStateSnapshot | None = None

    def _current_file_path(self) -> str | None:
        """Return the file path at the current cursor position in diff mode."""
        if not self._hunks or not self._content:
            return None
        target_hunk = None
        for h in self._hunks:
            if h.start <= self._i < h.end:
                target_hunk = h
                break
        if target_hunk is None:
            return None
        header_idx = target_hunk.file_header_start
        if header_idx >= len(self._content):
            return None
        line = self._content[header_idx]
        m = _DIFF_GIT_RE.match(line)
        if m:
            return m.group(2).strip('"')
        return None

    def _set_plain_content(self, lines: list[str]) -> None:
        """Set plain file content (no diff parsing) for File History mode."""
        self._content = []
        for line in lines:
            cleaned = plain(line).replace("\r", "")
            if "\t" in cleaned:
                cleaned = cleaned.expandtabs(self.TAB_WIDTH)
            self._content.append(cleaned)

        # Plain 1-based sequential line numbers
        self._line_numbers = [
            str(i + 1).rjust(self.LINE_NO_STR_WIDTH) for i in range(len(self._content))
        ]

        # Detect language from file path
        lang = "generic"
        if self._file_history_path:
            lang = self._tokenizer.detect_language(self._file_history_path)
        self._line_langs = [lang] * len(self._content)

        # No heatmap for plain files
        self._heatmap = [" "] * len(self._content)
        self._heatmap_colors = [THEME.fg_dim] * len(self._content)

        self._multiline_mask = self._tokenizer.compute_multiline_mask(
            self._content, self._line_langs, strip_diff_prefix=False
        )
        self._render_tokens = self._pre_tokenize_plain()
        self._hunks = []
        self._hunk_starts = []
        self._i = 0

    def _pre_tokenize_plain(self) -> list[list[tuple[str, tuple[int, int, int], int]]]:
        """Pre-tokenize plain file content (no diff prefixes)."""
        result: list[list[tuple[str, tuple[int, int, int], int]]] = []
        for i, line in enumerate(self._content):
            lang = self._line_langs[i] if i < len(self._line_langs) else "generic"
            ml_type = self._multiline_mask[i] if i < len(self._multiline_mask) else None
            if lang == "plain":
                tokens = [(line, "plain")]
            elif ml_type is not None:
                tokens = [(line, ml_type)]
            elif lang == "md":
                tokens = self._tokenizer.tokenize_markdown(line)
            else:
                tokens = self._tokenizer.tokenize(line, lang)
            result.append(
                [
                    (
                        text,
                        (
                            THEME.fg_primary
                            if ttype == "plain"
                            else self._tokenizer.resolve_color(ttype, lang)
                        ),
                        wcswidth(text),
                    )
                    for text, ttype in tokens
                ]
            )
        return result

    def set_content(self, diff_lines: list[str]) -> None:
        """Set diff content and pre-compute heatmap and line numbers.

        Tab characters are expanded to spaces (tabstop=8) because terminals
        render tabs as variable-width whitespace, while our width calculations
        treat every codepoint as width 1. Without expansion, tab-heavy diff
        lines overflow their allocated columns and corrupt borders.

        Carriage returns (``\\r``) are stripped because CRLF files cause
        ``\\r`` to reset the cursor to the start of the line, corrupting
        the rendered output.
        """
        self._content = []
        self._heatmap = []
        self._heatmap_colors = []
        self._line_numbers = []
        self._line_langs = []
        self._multiline_mask = []
        self._render_tokens = []
        self._hunks = []
        self._hunk_starts = []
        self._file_history_mode = False
        self._file_history_cache.clear()
        for line in diff_lines:
            cleaned = plain(line).replace("\r", "")
            if "\t" in cleaned:
                cleaned = cleaned.expandtabs(self.TAB_WIDTH)
            self._content.append(cleaned)
        self._compute_heatmap()
        self._compute_line_numbers()
        self._line_langs = self._detect_line_languages()
        self._multiline_mask = self._tokenizer.compute_multiline_mask(
            self._content, self._line_langs
        )
        self._render_tokens = self._pre_tokenize()
        self._hunks = self._parse_hunks()
        self._hunk_starts = [h.start for h in self._hunks]
        self._i = 0

    def set_diff_type(self, diff_type: DiffType) -> None:
        """Set the diff type (unstaged, staged, or commit)."""
        self._diff_type = diff_type

    def _parse_hunks(self) -> list[_Hunk]:
        """Parse hunk boundaries from diff content in a single pass."""
        hunks: list[_Hunk] = []
        current_start: int | None = None
        file_header_start = 0
        old_start = new_start = old_count = new_count = 0

        for i, line in enumerate(self._content):
            if line.startswith("diff --git"):
                if current_start is not None:
                    hunks.append(
                        _Hunk(
                            start=current_start,
                            end=i,
                            old_start=old_start,
                            old_count=old_count,
                            new_start=new_start,
                            new_count=new_count,
                            file_header_start=file_header_start,
                        )
                    )
                    current_start = None
                file_header_start = i
                continue

            if line.startswith("@@"):
                if current_start is not None:
                    hunks.append(
                        _Hunk(
                            start=current_start,
                            end=i,
                            old_start=old_start,
                            old_count=old_count,
                            new_start=new_start,
                            new_count=new_count,
                            file_header_start=file_header_start,
                        )
                    )
                current_start = i
                m = _HUNK_HEADER_RE.match(line)
                if m:
                    old_start = int(m.group(1))
                    new_start = int(m.group(2))
                    old_count = self._parse_count(line, is_old=True)
                    new_count = self._parse_count(line, is_old=False)
                else:
                    old_start = new_start = 0
                    old_count = new_count = 1

        if current_start is not None:
            hunks.append(
                _Hunk(
                    start=current_start,
                    end=len(self._content),
                    old_start=old_start,
                    old_count=old_count,
                    new_start=new_start,
                    new_count=new_count,
                    file_header_start=file_header_start,
                )
            )
        return hunks

    @staticmethod
    def _parse_count(header_line: str, *, is_old: bool) -> int:
        """Parse hunk count from @@ header. Per git diff spec, omitted count defaults to 1."""
        if is_old:
            pattern = r"-(\d+)(?:,(\d+))?"
        else:
            pattern = r"\+(\d+)(?:,(\d+))?"
        m = re.search(pattern, header_line)
        if not m:
            return 1
        count_str = m.group(2)
        return int(count_str) if count_str is not None else 1

    def _detect_line_languages(self) -> list[str]:
        """Scan file headers to determine per-line language.

        Lines before the first ``diff --git`` (commit meta-info) and diff
        file headers (``---`` / ``+++``) are marked as ``"plain"`` to skip
        syntax highlighting. Only actual code lines use language-specific
        tokenization.
        """
        result: list[str] = []
        current_lang = "generic"
        saw_diff = False
        for line in self._content:
            if line.startswith("diff --git"):
                saw_diff = True
                parts = line.split()
                if len(parts) >= 4 and parts[3].startswith("b/"):
                    current_lang = self._tokenizer.detect_language(parts[3][2:])
                result.append("plain")
            elif not saw_diff:
                result.append("plain")
            elif line.startswith("--- ") or line.startswith("+++ "):
                if line.startswith("+++ "):
                    filename = line[4:]
                    if filename.startswith("b/"):
                        filename = filename[2:]
                    current_lang = self._tokenizer.detect_language(filename)
                result.append("plain")
            else:
                result.append(current_lang)
        return result

    def _pre_tokenize(self) -> list[list[tuple[str, tuple[int, int, int], int]]]:
        """Pre-tokenize all lines, resolve colors, and compute display widths."""
        result: list[list[tuple[str, tuple[int, int, int], int]]] = []
        for i, line in enumerate(self._content):
            lang = self._line_langs[i] if i < len(self._line_langs) else "generic"
            if line.startswith("@@"):
                tokens = self._tokenizer.tokenize_diff_hunk(line)
            elif line.startswith("\\"):
                result.append([])
                continue
            else:
                if self._is_file_header(line):
                    code = line
                elif line and line[0] in "+- ":
                    code = line[1:]
                else:
                    code = line
                ml_type = (
                    self._multiline_mask[i] if i < len(self._multiline_mask) else None
                )
                if lang == "plain":
                    tokens = [(code, "plain")]
                elif ml_type is not None:
                    tokens = [(code, ml_type)]
                elif lang == "md":
                    tokens = self._tokenizer.tokenize_markdown(code)
                else:
                    tokens = self._tokenizer.tokenize(code, lang)
            result.append(
                [
                    (
                        text,
                        (
                            THEME.fg_primary
                            if ttype == "plain"
                            else self._tokenizer.resolve_color(ttype, lang)
                        ),
                        wcswidth(text),
                    )
                    for text, ttype in tokens
                ]
            )
        return result

    def get_help_title(self) -> str:
        return "Diff"

    def get_help_entries(self) -> list[tuple[str, str]]:
        """Return help pairs for diff viewer."""
        if self._file_history_mode:
            return [
                ("jk", "Scroll"),
                ("p", "Older commit"),
                ("n", "Newer commit"),
                ("d", "Diff view"),
                ("Esc", "Back"),
            ]
        if self._hunk_mode:
            return [
                ("jk", "Prev/Next hunk"),
                ("s", "Stage/Unstage hunk"),
                ("d", "Discard hunk"),
                ("H/Esc", "Exit hunk mode"),
            ]
        entries = [
            ("jk", "Navigate"),
            ("JK", "Quick Navigate"),
            ("] [", "Next/Prev hunk"),
            ("esc", "Back"),
        ]
        if self._diff_type is not DiffType.COMMIT:
            entries.insert(2, ("H", "Hunk mode"))
        else:
            entries.insert(2, ("v", "View file at commit"))
        return entries

    def update(self, action: ActionEventType, **data) -> None:
        if action is ActionEventType.goto:
            self.i_cache[self.i_cache_key] = self._i
            while len(self.i_cache) >= self._CACHE_MAX:
                del self.i_cache[next(iter(self.i_cache))]
            src = data.get("source")
            self.come_from = src if isinstance(src, Component) else None
            self.i_cache_key = data.get("key", "")
            self._repo_path = data.get("repo_path", "")
            raw_type = data.get("diff_type", "unstaged")
            if isinstance(raw_type, DiffType):
                self._diff_type = raw_type
            elif isinstance(raw_type, str):
                self._diff_type = DiffType(raw_type)
            else:
                self._diff_type = DiffType.UNSTAGED
            # Reset hunk mode on new diff
            self._hunk_mode = False
            self._hunk_index = 0
            content = data.get("content", "")
            match content:
                case list():
                    self.set_content(content)
                case str():
                    self.set_content(content.splitlines())
            self._i = self.i_cache.get(self.i_cache_key, 0)

    @bind_keys(keys.KEY_ESC)
    def _leave_display(self) -> None:
        if self._file_history_mode:
            self._exit_file_history()
            return
        if self._hunk_mode:
            self._hunk_mode = False
            return
        if self.come_from is not None:
            self.emit(ActionEventType.goto, target=self.come_from)

    @bind_keys("v")
    def _toggle_file_history(self) -> None:
        if self._file_history_mode:
            self._exit_file_history()
            return
        if self._diff_type is not DiffType.COMMIT:
            show_toast("File history only available for commit diffs", duration=1.5)
            return
        path = self._current_file_path()
        if not path:
            show_toast("No file at current position", duration=1.5)
            return
        self._enter_file_history(path)

    def _enter_file_history(self, path: str) -> None:
        """Save diff state and switch to File History view."""
        # Save BEFORE set_content overwrites everything
        self._saved_diff_state = _DiffStateSnapshot(
            content=list(self._content),
            diff_type=self._diff_type,
            scroll_i=self._i,
            come_from=self.come_from,
        )
        self._file_history_path = path
        self._file_history_cache = {}

        from .git.local_git import LocalGit

        git = LocalGit(path=self._repo_path)
        self._file_history_commits = git.get_file_history(path, self._repo_path)

        current_sha = self.i_cache_key
        self._file_history_index = 0
        for i, (sha, _) in enumerate(self._file_history_commits):
            if sha.startswith(current_sha) or current_sha.startswith(sha):
                self._file_history_index = i
                break

        self._file_history_mode = True
        self._load_file_history_at_current_index()

    def _load_file_history_at_current_index(self) -> None:
        if not self._file_history_commits:
            self._set_plain_content(["No history for this file"])
            return
        sha, _ = self._file_history_commits[self._file_history_index]

        if sha in self._file_history_cache:
            content = self._file_history_cache[sha]
        else:
            from .git.local_git import LocalGit

            git = LocalGit(path=self._repo_path)
            raw = git.get_file_at_commit(sha, self._file_history_path, self._repo_path)
            if raw is None:
                content = ["File deleted in this commit"]
            elif raw.startswith("\x00BINARY_OR_TOO_LARGE:"):
                parts = raw.split(":")
                size_str = parts[1].rstrip("\x00") if len(parts) > 1 else "?"
                if size_str.startswith("-"):
                    size_str = "unknown size"
                content = [f"Binary file ({size_str} bytes)"]
            else:
                content = raw.splitlines()
            self._file_history_cache[sha] = content
            # Simple LRU: trim to 10 entries
            if len(self._file_history_cache) > 10:
                oldest = next(iter(self._file_history_cache))
                del self._file_history_cache[oldest]

        self._set_plain_content(content)

    def _exit_file_history(self) -> None:
        if not self._file_history_mode:
            return
        self._file_history_mode = False
        self._file_history_cache.clear()
        snap = self._saved_diff_state
        if snap is not None:
            self.set_content(snap.content)
            self._diff_type = snap.diff_type
            self._i = snap.scroll_i
            self.come_from = snap.come_from
        self._saved_diff_state = None

    @bind_keys("p")
    def _prev_file_commit(self) -> None:
        """Go to older commit that touched this file."""
        if not self._file_history_mode:
            return
        if self._file_history_index < len(self._file_history_commits) - 1:
            self._file_history_index += 1
            self._load_file_history_at_current_index()

    @bind_keys("n")
    def _next_file_commit(self) -> None:
        """Go to newer commit that touched this file."""
        if not self._file_history_mode:
            return
        if self._file_history_index > 0:
            self._file_history_index -= 1
            self._load_file_history_at_current_index()

    @bind_keys("j")
    def _on_j(self) -> None:
        if self._hunk_mode:
            self._next_hunk_nav()
        else:
            self.scroll_down()

    @bind_keys("k")
    def _on_k(self) -> None:
        if self._hunk_mode:
            self._prev_hunk_nav()
        else:
            self.scroll_up()

    @bind_keys("J")
    def _scroll_page_down(self) -> None:
        self.scroll_down(self.SCROLL_PAGE_SIZE)

    @bind_keys("K")
    def _scroll_page_up(self) -> None:
        self.scroll_up(self.SCROLL_PAGE_SIZE)

    @bind_keys("]")
    def _next_hunk(self) -> None:
        """Jump to next hunk header (@@ line)."""
        if not self._hunk_starts:
            return
        pos = bisect.bisect_right(self._hunk_starts, self._i)
        if pos < len(self._hunk_starts):
            self._i = self._hunk_starts[pos]

    @bind_keys("[")
    def _prev_hunk(self) -> None:
        """Jump to previous hunk header (@@ line)."""
        if not self._hunk_starts:
            return
        pos = bisect.bisect_left(self._hunk_starts, self._i) - 1
        if pos >= 0:
            self._i = self._hunk_starts[pos]

    @bind_keys("H")
    def toggle_hunk_mode(self) -> None:
        if self._diff_type is DiffType.COMMIT:
            return
        if not self._hunks:
            show_toast("No hunks available", duration=1.5)
            return
        self._hunk_mode = not self._hunk_mode
        if self._hunk_mode:
            self._hunk_index = 0
            self._scroll_to_hunk(self._hunk_index)

    def _next_hunk_nav(self) -> None:
        self._hunk_index = min(self._hunk_index + 1, len(self._hunks) - 1)
        self._scroll_to_hunk(self._hunk_index)

    def _prev_hunk_nav(self) -> None:
        self._hunk_index = max(self._hunk_index - 1, 0)
        self._scroll_to_hunk(self._hunk_index)

    def _scroll_to_hunk(self, idx: int) -> None:
        """Scroll so hunk header is at top of viewport."""
        hunk = self._hunks[idx]
        self._i = max(0, hunk.start)

    def _run_hunk_action(self, action: str, *, needs_confirm: bool = False) -> None:
        if not self._hunks or self._diff_type is DiffType.COMMIT:
            show_toast("Not available for commit diffs", duration=1.5)
            return
        patch = self._extract_hunk_patch(self._hunk_index)
        if needs_confirm:

            def on_confirm(confirmed: bool) -> None:
                if confirmed:
                    self._apply_patch(patch, action=action)

            self._alert_dialog.alert("Discard hunk?", on_confirm)
        else:
            self._apply_patch(patch, action=action)

    @bind_keys("s")
    def _stage_current_hunk(self) -> None:
        self._run_hunk_action("stage")

    @bind_keys("d")
    def _discard_current_hunk(self) -> None:
        if self._file_history_mode:
            self._exit_file_history()
            return
        self._run_hunk_action("discard", needs_confirm=True)

    def _extract_hunk_patch(self, hunk_idx: int) -> str:
        """Extract file header + single hunk as a valid git patch.

        The file header includes everything from 'diff --git' up to (but not
        including) the first @@ line. Previous hunks in the same file are
        NOT included.
        """
        hunk = self._hunks[hunk_idx]

        header_lines: list[str] = []
        for i in range(hunk.file_header_start, hunk.start):
            header_lines.append(self._content[i])

        hunk_lines = [self._content[i] for i in range(hunk.start, hunk.end)]
        return "\n".join(header_lines + hunk_lines) + "\n"

    def _patch_cmd_and_msg(self, patch_path: str, action: str) -> tuple[list[str], str]:
        if action == "stage":
            if self._diff_type is DiffType.STAGED:
                return ["git", "apply", "--cached", "-R", patch_path], "Hunk unstaged"
            return ["git", "apply", "--cached", patch_path], "Hunk staged"
        return ["git", "apply", "-R", patch_path], "Hunk discarded"

    def _apply_patch(self, patch: str, action: str) -> None:
        """Apply or reverse-apply a patch using subprocess (no TUI flicker)."""
        if not self._repo_path:
            show_toast("No repo path available", duration=2.0)
            return

        suffix = "_stage.patch" if action == "stage" else "_discard.patch"
        with tempfile.NamedTemporaryFile(mode="w", suffix=suffix, delete=False) as f:
            f.write(patch)
            patch_path = f.name

        try:
            cmd, msg = self._patch_cmd_and_msg(patch_path, action)
            result = subprocess.run(cmd, cwd=self._repo_path, capture_output=True)
            if result.returncode == 0:
                show_badge(msg, duration=1.0)
            else:
                stderr = (
                    result.stderr.decode("utf-8", errors="replace")
                    if result.stderr
                    else ""
                )
                show_toast(f"Failed: {stderr[:100]}", duration=2.0)
        except Exception as e:
            show_toast(f"Failed: {e}", duration=2.0)
        finally:
            try:
                os.unlink(patch_path)
            except OSError:
                pass

    def _compute_heatmap(self) -> None:
        """Compute density symbol and color for each line."""
        self._heatmap = []
        self._heatmap_colors = []
        for line in self._content:
            sym, color = self._heatmap_entry(line)
            self._heatmap.append(sym)
            self._heatmap_colors.append(color)

    def _heatmap_entry(self, line: str) -> tuple[str, tuple[int, int, int]]:
        """Return (density_symbol, color) for a single diff line."""
        if self._is_file_header(line):
            return " ", THEME.fg_dim
        if self._is_add_line(line):
            density = self._line_density(line)
            return (
                ["░", "▒", "▓", "█"][min(density, 3)],
                THEME.fg_success,
            )
        if self._is_del_line(line):
            density = self._line_density(line)
            return (
                ["░", "▒", "▓", "█"][min(density, 3)],
                THEME.fg_danger,
            )
        return " ", THEME.fg_dim

    def _line_density(self, line: str) -> int:
        """Heuristic density based on line length."""
        length = len(line.strip())
        if length < self.DENSITY_SHORT:
            return 0
        if length < self.DENSITY_MEDIUM:
            return 1
        if length < self.DENSITY_LONG:
            return 2
        return 3

    def _compute_line_numbers(self) -> None:
        """Compute line numbers for each diff line by parsing @@ headers."""
        self._line_numbers = []
        old_line = 0
        new_line = 0
        for line in self._content:
            if line.startswith("@@"):
                m = _HUNK_HEADER_RE.search(line)
                if m:
                    old_line = int(m.group(1))
                    new_line = int(m.group(2))
                else:
                    _logger.warning("Unexpected @@ line format: %r", line)
                    old_line = 0
                    new_line = 0
                self._line_numbers.append("")
            elif self._is_file_header(line):
                self._line_numbers.append("")
            elif self._is_add_line(line):
                self._line_numbers.append(str(new_line).rjust(self.LINE_NO_STR_WIDTH))
                new_line += 1
            elif self._is_del_line(line):
                self._line_numbers.append(str(old_line).rjust(self.LINE_NO_STR_WIDTH))
                old_line += 1
            elif line.startswith("\\"):
                self._line_numbers.append("")
            else:
                # Context line
                self._line_numbers.append(str(new_line).rjust(self.LINE_NO_STR_WIDTH))
                old_line += 1
                new_line += 1

    def resize(self, size: tuple[int, int]) -> None:
        # Reserve BORDER_ROWS for top/bottom borders
        self._max_line = max(0, size[1] - self.BORDER_ROWS)
        # Bypass LineTextBrowser.resize() which would reset _max_line to full height
        super(LineTextBrowser, self).resize(size)

    def _draw_diff_line(
        self,
        surface,
        row: int,
        line: str,
        idx: int,
        *,
        x_offset: int,
        main_w: int,
        heatmap_x: int,
        fill_width: int,
    ) -> None:
        """Render one diff line: background, line number, text, and heatmap."""
        is_add = self._is_add_line(line)
        is_del = self._is_del_line(line)

        if is_add:
            bg = THEME.bg_success
        elif is_del:
            bg = THEME.bg_danger
        else:
            bg = THEME.bg_diff_context

        # Hunk mode highlight: override bg for active hunk
        if self._hunk_mode and self._hunks:
            hunk = self._hunks[self._hunk_index]
            if hunk.start <= idx < hunk.end:
                bg = THEME.bg_info

        if bg != THEME.bg_diff_context:
            surface.fill_rect_rgb(row, x_offset, fill_width, 1, bg)

        line_no = self._line_numbers[idx] if idx < len(self._line_numbers) else ""
        if line_no:
            surface.draw_text_rgb(row, x_offset, line_no, fg=THEME.fg_dim, bg=bg)

        prefix_x = x_offset + self.LINE_NO_WIDTH
        if is_add:
            surface.draw_text_rgb(row, prefix_x, "+", fg=THEME.fg_success, bg=bg)
        elif is_del:
            surface.draw_text_rgb(row, prefix_x, "-", fg=THEME.fg_danger, bg=bg)

        # ── Syntax-highlighted text rendering ──
        text_start_col = x_offset + self.LINE_NO_WIDTH + self.DIFF_PREFIX_WIDTH
        col = text_start_col
        max_col = text_start_col + main_w
        tokens: list[tuple[str, tuple[int, int, int], int]] = []

        if line.startswith("\\"):
            surface.draw_text_rgb(row, text_start_col, line, fg=THEME.fg_dim, bg=bg)
        else:
            tokens = self._render_tokens[idx]

        self._draw_tokens(surface, row, col, max_col, tokens, bg)

        sym = self._heatmap[idx]
        color = self._heatmap_colors[idx]
        surface.draw_text_rgb(row, heatmap_x, sym, fg=color, bg=bg)

    def _draw_tokens(
        self,
        surface,
        row: int,
        col: int,
        max_col: int,
        tokens: list[tuple[str, tuple[int, int, int], int]],
        bg: tuple[int, int, int] | None = None,
    ) -> None:
        """Draw syntax tokens with width-aware truncation."""
        for token_text, token_fg, token_width in tokens:
            if col + token_width > max_col:
                avail = max_col - col
                if avail > 1:
                    token_text = truncate_by_width(token_text, avail - 1) + "…"
                    surface.draw_text_rgb(row, col, token_text, fg=token_fg, bg=bg)
                break
            surface.draw_text_rgb(row, col, token_text, fg=token_fg, bg=bg)
            col += token_width

    def _file_history_header(self) -> str:
        """Build the header line for File History view."""
        if not self._file_history_commits:
            return f" {self._file_history_path} — no history "
        sha, subject = self._file_history_commits[self._file_history_index]
        short_sha = sha[:8]
        pos = f"({self._file_history_index + 1}/{len(self._file_history_commits)})"
        # Truncate subject if too long
        max_subj = 40
        if len(subject) > max_subj:
            subject = subject[: max_subj - 1] + "…"
        return f' {self._file_history_path}  @  {short_sha}  "{subject}"  {pos} '

    def _render_file_history(self, surface) -> None:
        if not self._content:
            return
        w = surface.width
        h = surface.height
        if w <= self.LINE_NO_WIDTH + 3 or h < self.BORDER_ROWS + 1:
            self._render_file_history_borderless(surface)
            return

        surface.draw_box_rgb(0, 0, w, h, fg=THEME.fg_dim)

        # Header row (overwrites top border)
        header = self._file_history_header()
        header_trim = (
            truncate_by_width(header, w - 4) + " "
            if wcswidth(header) > w - 4
            else header
        )
        surface.draw_text_rgb(
            0,
            2,
            header_trim,
            fg=THEME.fg_file_history_header,
            bg=THEME.bg_file_history_header,
            style_flags=palette.STYLE_BOLD,
        )

        # Content area
        content_h = h - self.BORDER_ROWS  # rows between top and bottom borders
        content_w = w - self.BORDER_COLS
        main_w = content_w - self.LINE_NO_WIDTH - 1
        end = min(self._i + content_h, len(self._content))

        for idx in range(self._i, end):
            row = idx - self._i + 1  # +1 for top border

            line_no = self._line_numbers[idx] if idx < len(self._line_numbers) else ""
            if line_no:
                surface.draw_text_rgb(row, 1, line_no, fg=THEME.fg_dim)

            text_start = 1 + self.LINE_NO_WIDTH + 1
            tokens = self._render_tokens[idx] if idx < len(self._render_tokens) else []
            self._draw_tokens(
                surface,
                row,
                text_start,
                text_start + main_w,
                tokens,
            )

        # Footer hint (overwrites bottom border)
        hint = " jk:nav  p:older  n:newer  d:diff  Esc:back "
        hint_trim = truncate_by_width(hint, w - 4) if wcswidth(hint) > w - 4 else hint
        surface.draw_text_rgb(h - 1, 1, hint_trim, fg=THEME.fg_dim)

    def _render_file_history_borderless(self, surface) -> None:
        """File history rendering when surface is too small for borders."""
        w = surface.width
        h = surface.height
        if w <= self.LINE_NO_WIDTH + 1:
            return

        main_w = self._main_width(w)
        end = min(self._i + h, len(self._content))

        for idx in range(self._i, end):
            row = idx - self._i

            line_no = self._line_numbers[idx] if idx < len(self._line_numbers) else ""
            if line_no:
                surface.draw_text_rgb(row, 0, line_no, fg=THEME.fg_dim)

            text_start = self.LINE_NO_WIDTH + 1
            tokens = self._render_tokens[idx] if idx < len(self._render_tokens) else []
            self._draw_tokens(
                surface,
                row,
                text_start,
                text_start + main_w,
                tokens,
            )

    def _render_surface(self, surface) -> None:
        if not self._content:
            return
        if self._file_history_mode:
            self._render_file_history(surface)
            return
        w = surface.width
        h = surface.height
        if w <= self.LINE_NO_WIDTH + 3 or h < self.BORDER_ROWS + 1:
            self._render_surface_borderless(surface)
            return

        surface.draw_box_rgb(0, 0, w, h, fg=THEME.fg_dim)

        content_h = h - self.BORDER_ROWS
        content_w = w - self.BORDER_COLS
        main_w = self._main_width(content_w)
        end = min(self._i + content_h, len(self._content))

        for idx in range(self._i, end):
            row = idx - self._i + 1
            self._draw_diff_line(
                surface,
                row,
                self._content[idx],
                idx,
                x_offset=1,
                main_w=main_w,
                heatmap_x=w - self.BORDER_COLS,
                fill_width=w - self.BORDER_COLS,
            )

        last_content_row = end - self._i
        blank_count = h - 1 - (last_content_row + 1)
        if blank_count > 0:
            surface.fill_rect_rgb(
                last_content_row + 1,
                1,
                w - self.BORDER_COLS,
                blank_count,
                THEME.bg_diff_context,
            )

        if self._hunk_mode:
            badge = " HUNK "
            badge_x = w - len(badge) - 2
            if badge_x > 0:
                surface.draw_text_rgb(
                    h - 1,
                    badge_x,
                    badge,
                    fg=THEME.fg_file_history_link,
                    style_flags=palette.STYLE_BOLD,
                )

    def _render_surface_borderless(self, surface) -> None:
        """Original rendering without box border, used when surface is too small."""
        w = surface.width
        h = surface.height
        if w <= self.LINE_NO_WIDTH + 1:
            return

        main_w = self._main_width(w)
        end = min(self._i + h, len(self._content))

        for idx in range(self._i, end):
            row = idx - self._i
            self._draw_diff_line(
                surface,
                row,
                self._content[idx],
                idx,
                x_offset=0,
                main_w=main_w,
                heatmap_x=w - 1,
                fill_width=w,
            )
