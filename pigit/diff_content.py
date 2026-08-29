"""
Module: pigit/diff_content.py
Description: Sync unified-diff / plain-file structure for DiffViewer (no Git).
Author: Zev
Date: 2026-08-24
"""

from __future__ import annotations

import dataclasses
import difflib
import logging
import re

from pigit.termui import palette
from pigit.termui.primitives import (
    format_line_number,
    merge_ranges,
    plain,
    tokenize_with_positions,
)
from pigit.termui.syntax import SyntaxTokenizer
from pigit.termui.wcwidth_table import wcswidth

from .app_theme import THEME

_logger = logging.getLogger(__name__)

_HUNK_HEADER_RE = re.compile(r"@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@")

# A render token is (text, fg_rgb, display_width, word_diff_bg_or_None, style_flags).
RenderToken = tuple[str, tuple[int, int, int], int, tuple[int, int, int] | None, int]
RenderLine = list[RenderToken]
WordDiffSegment = tuple[str, str | None, int]


@dataclasses.dataclass
class Hunk:
    """A single diff hunk boundary."""

    start: int  # index into lines (includes @@ line)
    end: int  # index into lines (excludes next @@ or EOF)
    old_start: int
    old_count: int
    new_start: int
    new_count: int
    file_header_start: int  # index of 'diff --git' line for this file


@dataclasses.dataclass
class DiffContent:
    """Parsed diff or plain-file structure consumed by DiffViewer.

    Syntax tokens for large diffs are produced asynchronously by the viewer
    via :meth:`pre_tokenize_with`; this type only owns sync structure.
    """

    TAB_WIDTH = 8
    LINE_NO_STR_WIDTH = 4
    DENSITY_SHORT = 10
    DENSITY_MEDIUM = 30
    DENSITY_LONG = 60

    lines: list[str]
    hunks: list[Hunk]
    heatmap: list[str]
    heatmap_colors: list[tuple[int, int, int]]
    line_numbers: list[str]
    line_langs: list[str]
    multiline_mask: list[str | None]
    word_diff_segments: list[list[WordDiffSegment]]

    @property
    def hunk_starts(self) -> list[int]:
        """Start indices of each hunk (for navigation)."""
        return [h.start for h in self.hunks]

    @classmethod
    def from_diff_lines(
        cls,
        diff_lines: list[str],
        *,
        word_diff: bool,
        tokenizer: SyntaxTokenizer,
    ) -> DiffContent:
        """Build structure from a unified diff (tabs expanded, CR stripped)."""
        lines: list[str] = []
        for line in diff_lines:
            cleaned = plain(line).replace("\r", "")
            if "\t" in cleaned:
                cleaned = cleaned.expandtabs(cls.TAB_WIDTH)
            lines.append(cleaned)

        hunks = cls._parse_hunks(lines)
        heatmap: list[str] = []
        heatmap_colors: list[tuple[int, int, int]] = []
        for line in lines:
            sym, color = cls._heatmap_entry(line)
            heatmap.append(sym)
            heatmap_colors.append(color)

        line_numbers = cls._compute_line_numbers(lines)
        line_langs = cls._detect_line_languages(lines, tokenizer)
        multiline_mask = tokenizer.compute_multiline_mask(lines, line_langs)
        word_diff_segments: list[list[WordDiffSegment]] = [[] for _ in lines]
        if word_diff:
            cls._fill_word_diff_segments(lines, hunks, word_diff_segments)

        return cls(
            lines=lines,
            hunks=hunks,
            heatmap=heatmap,
            heatmap_colors=heatmap_colors,
            line_numbers=line_numbers,
            line_langs=line_langs,
            multiline_mask=multiline_mask,
            word_diff_segments=word_diff_segments,
        )

    @classmethod
    def from_plain_lines(
        cls,
        plain_lines: list[str],
        *,
        language: str,
        tokenizer: SyntaxTokenizer,
    ) -> DiffContent:
        """Build structure for File History (no hunks; sequential line numbers)."""
        lines: list[str] = []
        for line in plain_lines:
            cleaned = plain(line).replace("\r", "")
            if "\t" in cleaned:
                cleaned = cleaned.expandtabs(cls.TAB_WIDTH)
            lines.append(cleaned)

        line_numbers = [
            format_line_number(i + 1, cls.LINE_NO_STR_WIDTH) for i in range(len(lines))
        ]
        line_langs = [language] * len(lines)
        return cls(
            lines=lines,
            hunks=[],
            heatmap=[" "] * len(lines),
            heatmap_colors=[THEME.fg_dim] * len(lines),
            line_numbers=line_numbers,
            line_langs=line_langs,
            multiline_mask=tokenizer.compute_multiline_mask(
                lines, line_langs, strip_diff_prefix=False
            ),
            word_diff_segments=[[] for _ in lines],
        )

    def pre_tokenize_plain(self, tokenizer: SyntaxTokenizer) -> list[RenderLine]:
        """Pre-tokenize plain file content (no diff prefixes) — sync path."""
        result: list[RenderLine] = []
        for i, line in enumerate(self.lines):
            lang = self.line_langs[i] if i < len(self.line_langs) else "generic"
            ml_type = self.multiline_mask[i] if i < len(self.multiline_mask) else None
            if lang == "plain":
                tokens = [(line, "plain")]
            elif ml_type is not None:
                tokens = [(line, ml_type)]
            elif lang == "md":
                tokens = tokenizer.tokenize_markdown(line)
            else:
                tokens = tokenizer.tokenize(line, lang)
            result.append(
                [
                    (
                        text,
                        (
                            THEME.fg_primary
                            if ttype == "plain"
                            else tokenizer.resolve_color(ttype, lang)
                        ),
                        wcswidth(text),
                        None,
                        0,
                    )
                    for text, ttype in tokens
                ]
            )
        return result

    @staticmethod
    def is_file_header(line: str) -> bool:
        """True for ``---`` / ``+++`` file headers."""
        return line.startswith("--- ") or line.startswith("+++ ")

    @staticmethod
    def is_add_line(line: str) -> bool:
        """True for added diff lines (not ``+++`` headers)."""
        return line.startswith("+") and not line.startswith("+++")

    @staticmethod
    def is_del_line(line: str) -> bool:
        """True for deleted diff lines (not ``---`` headers)."""
        return line.startswith("-") and not line.startswith("---")

    @staticmethod
    def word_diff_ranges(
        old: str, new: str
    ) -> tuple[list[tuple[int, int]], list[tuple[int, int]]]:
        """Return changed (start, end) ranges in ``old`` and ``new``."""
        old_tokens, old_positions = tokenize_with_positions(old)
        new_tokens, new_positions = tokenize_with_positions(new)

        matcher = difflib.SequenceMatcher(None, old_tokens, new_tokens, autojunk=False)
        matches = matcher.get_matching_blocks()

        del_ranges: list[tuple[int, int]] = []
        add_ranges: list[tuple[int, int]] = []
        old_tok = 0
        new_tok = 0
        for m in matches:
            if old_tok < m.a:
                start = old_positions[old_tok][0]
                end = old_positions[m.a - 1][1]
                del_ranges.append((start, end))
            if new_tok < m.b:
                start = new_positions[new_tok][0]
                end = new_positions[m.b - 1][1]
                add_ranges.append((start, end))
            old_tok = m.a + m.size
            new_tok = m.b + m.size

        del_ranges = merge_ranges(del_ranges)
        add_ranges = merge_ranges(add_ranges)
        return del_ranges, add_ranges

    @staticmethod
    def ranges_to_segments(
        text: str, ranges: list[tuple[int, int]], kind: str
    ) -> list[WordDiffSegment]:
        """Split ``text`` into unchanged / changed segments from sorted ranges."""
        segments: list[WordDiffSegment] = []
        last = 0
        for start, end in ranges:
            if start > last:
                segments.append((text[last:start], None, wcswidth(text[last:start])))
            segments.append((text[start:end], kind, wcswidth(text[start:end])))
            last = end
        if last < len(text):
            segments.append((text[last:], None, wcswidth(text[last:])))
        return segments

    @staticmethod
    def pre_tokenize_with(
        content: list[str],
        line_langs: list[str],
        multiline_mask: list[str | None],
        tokenizer: SyntaxTokenizer,
        word_diff_segments: list[list[WordDiffSegment]] | None = None,
    ) -> list[RenderLine]:
        """Pre-tokenize all lines with a state snapshot (thread-safe, no viewer self)."""
        result: list[RenderLine] = []
        for i, line in enumerate(content):
            lang = line_langs[i] if i < len(line_langs) else "generic"
            if line.startswith("@@"):
                tokens = tokenizer.tokenize_diff_hunk(line)
                result.append(
                    [
                        (
                            text,
                            (
                                THEME.fg_primary
                                if ttype == "plain"
                                else tokenizer.resolve_color(ttype, lang)
                            ),
                            wcswidth(text),
                            None,
                            0,
                        )
                        for text, ttype in tokens
                    ]
                )
                continue
            if line.startswith("\\"):
                result.append([])
                continue

            if line.startswith("--- ") or line.startswith("+++ "):
                code = line
            elif line and line[0] in "+- ":
                code = line[1:]
            else:
                code = line
            ml_type = multiline_mask[i] if i < len(multiline_mask) else None

            segments = (
                word_diff_segments[i]
                if word_diff_segments
                and i < len(word_diff_segments)
                and word_diff_segments[i]
                else None
            )
            if segments is not None:
                line_result: RenderLine = []
                for seg_text, seg_kind, _ in segments:
                    if lang == "plain":
                        seg_tokens = [(seg_text, "plain")]
                    elif ml_type is not None:
                        seg_tokens = [(seg_text, ml_type)]
                    elif lang == "md":
                        seg_tokens = tokenizer.tokenize_markdown(seg_text)
                    else:
                        seg_tokens = tokenizer.tokenize(seg_text, lang)
                    seg_bg = None
                    if seg_kind == "add":
                        seg_bg = THEME.bg_word_diff_add
                    elif seg_kind == "del":
                        seg_bg = THEME.bg_word_diff_del
                    for text, ttype in seg_tokens:
                        fg = (
                            THEME.fg_primary
                            if ttype == "plain"
                            else tokenizer.resolve_color(ttype, lang)
                        )
                        line_result.append(
                            (
                                text,
                                fg,
                                wcswidth(text),
                                seg_bg,
                                palette.STYLE_ITALIC if seg_bg is not None else 0,
                            )
                        )
                result.append(line_result)
                continue

            if lang == "plain":
                tokens = [(code, "plain")]
            elif ml_type is not None:
                tokens = [(code, ml_type)]
            elif lang == "md":
                tokens = tokenizer.tokenize_markdown(code)
            else:
                tokens = tokenizer.tokenize(code, lang)
            result.append(
                [
                    (
                        text,
                        (
                            THEME.fg_primary
                            if ttype == "plain"
                            else tokenizer.resolve_color(ttype, lang)
                        ),
                        wcswidth(text),
                        None,
                        0,
                    )
                    for text, ttype in tokens
                ]
            )
        return result

    @classmethod
    def _parse_hunks(cls, content: list[str]) -> list[Hunk]:
        """Parse hunk boundaries from diff content in a single pass."""
        hunks: list[Hunk] = []
        current_start: int | None = None
        file_header_start = 0
        old_start = new_start = old_count = new_count = 0

        for i, line in enumerate(content):
            if line.startswith("diff --git"):
                if current_start is not None:
                    hunks.append(
                        Hunk(
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
                        Hunk(
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
                    old_count = cls._parse_count(line, is_old=True)
                    new_count = cls._parse_count(line, is_old=False)
                else:
                    old_start = new_start = 0
                    old_count = new_count = 1

        if current_start is not None:
            hunks.append(
                Hunk(
                    start=current_start,
                    end=len(content),
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
        """Parse hunk count from @@ header. Omitted count defaults to 1."""
        if is_old:
            pattern = r"-(\d+)(?:,(\d+))?"
        else:
            pattern = r"\+(\d+)(?:,(\d+))?"
        m = re.search(pattern, header_line)
        if not m:
            return 1
        count_str = m.group(2)
        return int(count_str) if count_str is not None else 1

    @classmethod
    def _detect_line_languages(
        cls, content: list[str], tokenizer: SyntaxTokenizer
    ) -> list[str]:
        """Scan file headers to determine per-line language."""
        result: list[str] = []
        current_lang = "generic"
        saw_diff = False
        for line in content:
            if line.startswith("diff --git"):
                saw_diff = True
                parts = line.split()
                if len(parts) >= 4 and parts[3].startswith("b/"):
                    current_lang = tokenizer.detect_language(parts[3][2:])
                result.append("plain")
            elif not saw_diff:
                result.append("plain")
            elif line.startswith("--- ") or line.startswith("+++ "):
                if line.startswith("+++ "):
                    filename = line[4:]
                    if filename.startswith("b/"):
                        filename = filename[2:]
                    current_lang = tokenizer.detect_language(filename)
                result.append("plain")
            else:
                result.append(current_lang)
        return result

    @classmethod
    def _heatmap_entry(cls, line: str) -> tuple[str, tuple[int, int, int]]:
        """Return (density_symbol, color) for a single diff line."""
        if cls.is_file_header(line):
            return " ", THEME.fg_dim
        if cls.is_add_line(line):
            density = cls._line_density(line)
            return (
                ["░", "▒", "▓", "█"][min(density, 3)],
                THEME.fg_success,
            )
        if cls.is_del_line(line):
            density = cls._line_density(line)
            return (
                ["░", "▒", "▓", "█"][min(density, 3)],
                THEME.fg_danger,
            )
        return " ", THEME.fg_dim

    @classmethod
    def _line_density(cls, line: str) -> int:
        """Heuristic density based on line length."""
        length = len(line.strip())
        if length < cls.DENSITY_SHORT:
            return 0
        if length < cls.DENSITY_MEDIUM:
            return 1
        if length < cls.DENSITY_LONG:
            return 2
        return 3

    @classmethod
    def _compute_line_numbers(cls, content: list[str]) -> list[str]:
        """Compute line numbers for each diff line by parsing @@ headers."""
        line_numbers: list[str] = []
        old_line = 0
        new_line = 0
        for line in content:
            if line.startswith("@@"):
                m = _HUNK_HEADER_RE.search(line)
                if m:
                    old_line = int(m.group(1))
                    new_line = int(m.group(2))
                else:
                    _logger.warning("Unexpected @@ line format: %r", line)
                    old_line = 0
                    new_line = 0
                line_numbers.append("")
            elif cls.is_file_header(line):
                line_numbers.append("")
            elif cls.is_add_line(line):
                line_numbers.append(format_line_number(new_line, cls.LINE_NO_STR_WIDTH))
                new_line += 1
            elif cls.is_del_line(line):
                line_numbers.append(format_line_number(old_line, cls.LINE_NO_STR_WIDTH))
                old_line += 1
            elif line.startswith("\\"):
                line_numbers.append("")
            else:
                line_numbers.append(format_line_number(new_line, cls.LINE_NO_STR_WIDTH))
                old_line += 1
                new_line += 1
        return line_numbers

    @classmethod
    def _fill_word_diff_segments(
        cls,
        content: list[str],
        hunks: list[Hunk],
        segments: list[list[WordDiffSegment]],
    ) -> None:
        """Pair ``-``/``+`` lines inside each hunk and fill word segments."""
        for hunk in hunks:
            minus_idxs: list[int] = []
            plus_idxs: list[int] = []
            for idx in range(hunk.start + 1, hunk.end):
                line = content[idx]
                if line.startswith("-") and not line.startswith("--- "):
                    minus_idxs.append(idx)
                elif line.startswith("+") and not line.startswith("+++ "):
                    plus_idxs.append(idx)

            paired = min(len(minus_idxs), len(plus_idxs))
            for i in range(paired):
                old_idx = minus_idxs[i]
                new_idx = plus_idxs[i]
                old_code = content[old_idx][1:]
                new_code = content[new_idx][1:]
                del_ranges, add_ranges = cls.word_diff_ranges(old_code, new_code)
                segments[old_idx] = cls.ranges_to_segments(old_code, del_ranges, "del")
                segments[new_idx] = cls.ranges_to_segments(new_code, add_ranges, "add")
