"""
Module: pigit/termui/primitives/word_diff.py
Description: Word-level diff tokenization and range merging for highlight segments.
Author: Zev
Date: 2026-08-20
"""

from __future__ import annotations

import re

# ``git diff --word-diff`` splits on whitespace: a run of non-whitespace is one
# word. Whitespace itself is a separator, never a word, so it is not tokenised
# and can never be marked on its own.
_WORD_RE = re.compile(r"\S+")


def tokenize_with_positions(
    text: str,
) -> tuple[list[str], list[tuple[int, int]]]:
    """Split ``text`` into whitespace-delimited word tokens.

    Matches ``git diff --word-diff``'s default word splitting: a run of
    non-whitespace is a single token, so ``foo.bar`` changes as one unit (as
    it does in git) and indentation alone never produces a token — and thus
    never a highlight.

    Args:
        text: Source string to tokenize.

    Returns:
        Tuple of token strings and ``(start, end)`` spans in ``text``.
    """
    matches = list(_WORD_RE.finditer(text))
    tokens = [match.group(0) for match in matches]
    positions = [(match.start(), match.end()) for match in matches]
    return tokens, positions


def merge_ranges(
    ranges: list[tuple[int, int]],
) -> list[tuple[int, int]]:
    """Merge adjacent or overlapping ranges in sorted order.

    Args:
        ranges: Sorted ``(start, end)`` character ranges.

    Returns:
        Merged non-overlapping ranges in ascending order.
    """
    if not ranges:
        return []
    result: list[tuple[int, int]] = []
    cur_start, cur_end = ranges[0]
    for start, end in ranges[1:]:
        if start <= cur_end:
            cur_end = max(cur_end, end)
        else:
            result.append((cur_start, cur_end))
            cur_start, cur_end = start, end
    result.append((cur_start, cur_end))
    return result
