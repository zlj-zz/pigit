"""
Module: pigit/termui/_word_diff.py
Description: Word-level diff tokenization and range merging for highlight segments.
Author: Zev
Date: 2026-08-20
"""

from __future__ import annotations


def tokenize_with_positions(
    text: str,
) -> tuple[list[str], list[tuple[int, int]]]:
    """Split ``text`` into tokens at whitespace and word-boundary points.

    A word character is ``[a-zA-Z0-9_]`` (``str.isalnum()`` plus underscore);
    transitions between word and non-word characters produce a split.  This
    matches ``diff-highlight`` tokenisation so that e.g.
    ``foo.bar`` → ``["foo", ".", "bar"]`` and only the truly changed
    sub-tokens are highlighted.

    Args:
        text: Source string to tokenize.

    Returns:
        Tuple of token strings and ``(start, end)`` spans in ``text``.
    """

    def _is_word(character: str) -> bool:
        return character.isalnum() or character == "_"

    tokens: list[str] = []
    positions: list[tuple[int, int]] = []
    index = 0
    length = len(text)
    while index < length:
        if text[index].isspace():
            start = index
            while index < length and text[index].isspace():
                index += 1
            tokens.append(text[start:index])
            positions.append((start, index))
            continue

        start = index
        if _is_word(text[index]):
            while index < length and _is_word(text[index]):
                index += 1
        else:
            while (
                index < length
                and not text[index].isspace()
                and not _is_word(text[index])
            ):
                index += 1
        tokens.append(text[start:index])
        positions.append((start, index))
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
