# -*- coding: utf-8 -*-
"""
Module: tests/termui/test_wcwidth_table.py
Description: Display-width helpers, especially left-slicing by columns.
Author: Zev
Date: 2026-09-28
"""

from __future__ import annotations

import pytest

from pigit.termui.wcwidth_table import (
    slice_left_by_width,
    truncate_by_width,
    wcswidth,
)

#: "e" + U+0301 (combining acute), used to check marks stay with their base.
ACCENTED = "é"

CASES = [
    ("中文abc", 2, "文abc"),
    ("中文abc", 4, "abc"),
    ("中文", 0, "中文"),
    ("中文", 3, " "),  # cut inside 文: one column survives, drawn blank
    ("中", 1, " "),
    ("a中", 2, " "),
    ("abc", 5, ""),
    ("abc", 3, ""),
    ("", 3, ""),
    # Combining marks
    (f"{ACCENTED}x", 1, "x"),  # base dropped, mark goes with it
    ("中́x", 2, "x"),  # same, after a half-cut wide glyph
    (f"a{ACCENTED}x", 1, f"{ACCENTED}x"),  # mark keeps its base
    # VS16 emoji: two columns, selector folded into the base
    ("❤️x", 1, " x"),  # cut inside it: one column survives, drawn blank
    ("❤️x", 2, "x"),  # cut after it: the orphan selector goes too
    # ZWJ and skin-tone clusters measure two columns; slicing must agree
    ("👩‍💻x", 1, " x"),
    ("👩‍💻x", 2, "x"),
    ("👩‍💻x", 3, ""),
    ("👍🏽x", 2, "x"),
]


@pytest.mark.parametrize("text, skip, expected", CASES)
def test_slice_left_by_width(text, skip, expected):
    assert slice_left_by_width(text, skip) == expected


@pytest.mark.parametrize("text, skip, _expected", CASES)
def test_slice_preserves_the_width_invariant(text, skip, _expected):
    """Callers lay out what follows by column, so the result must be exactly
    ``width - skip`` columns wide — never less, or the rest of the line shifts
    left by the difference."""
    result = slice_left_by_width(text, skip)
    assert wcswidth(result) == max(0, wcswidth(text) - skip)


def test_slice_keeps_a_combining_mark_with_its_base():
    """A mark survives whenever the cut lands before its base."""
    assert slice_left_by_width(f"a{ACCENTED}x", 1) == f"{ACCENTED}x"


def test_slice_drops_a_mark_whose_base_was_cut_away():
    """This used to return the bare mark. A terminal then draws it over
    the blank or the previous word, which reads as a stray accent."""
    assert slice_left_by_width(f"{ACCENTED}x", 1) == "x"


def test_slice_drops_a_mark_left_behind_by_a_half_cut_glyph():
    """The blank that replaces a half-cut wide glyph is not a base either."""
    assert slice_left_by_width("中́x", 2) == "x"


def test_negative_skip_returns_text_unchanged():
    assert slice_left_by_width("中文", -1) == "中文"


def test_truncate_never_splits_a_selector_from_its_base():
    """A lone base or lone selector is a different glyph than the pair."""
    assert truncate_by_width("❤️a", 2) == "❤️"
    assert truncate_by_width("❤️a", 1) == ""


#: (text, columns, what the row pins). The combining rows are decomposed
#: sequences -- base plus mark -- not the precomposed character they resemble.
WIDTH_CASES = [
    ("abc", 3, "ASCII"),
    ("中文", 4, "CJK"),
    ("Ａ", 2, "fullwidth"),
    ("ｦ", 1, "halfwidth: H is not wide"),
    ("☕", 2, "single-code-point W emoji"),
    ("✅", 2, "single-code-point W emoji"),
    ("が", 2, "combining checked before east_asian_width"),
    ("é", 1, "combining acute"),
    ("ְ", 0, "Hebrew niqqud"),
    ("͏", 0, "CGJ: Mn with combining() == 0"),
    ("〮", 0, "Mc with combining() != 0"),
    ("1️⃣", 2, "keycap: digit widened by VS16, enclosing mark zero"),
    ("❤️", 2, "VS16 promotes a one-column base to an emoji"),
    ("❤", 1, "the same base without its selector stays narrow"),
    ("a❤️b", 4, "the promotion is positional, not a constant"),
    ("A️", 1, "VS16 after a base outside UTS #51 widens nothing"),
    ("✅︎", 2, "known gap: VS15 text presentation still counts wide"),
    ("\U0001f1fa\U0001f1f8", 2, "two regional indicators"),
    ("\x0e", 1, "C0 control"),
    ("\x7f", 1, "DEL"),
    ("\x9b", 1, "C1 control"),
    ("\u093e", 1, "spacing mark: Mc with ccc == 0"),
    ("\u200b", 0, "ZWSP: invisible format character"),
    ("\ufeff", 0, "BOM: invisible format character"),
    ("\u00ad", 1, "soft hyphen: Cf, but it can draw"),
    ("\u0600", 1, "Arabic number sign: Cf, but it draws"),
    ("\U0001f469\u200d\U0001f4bb", 2, "ZWJ: the joined glyph adds no column"),
    (
        "\U0001f468\u200d\U0001f469\u200d\U0001f467",
        2,
        "three emoji joined by ZWJ are one glyph",
    ),
    ("\U0001f44d\U0001f3fd", 2, "skin-tone modifier folds into its base"),
    (
        "\U0001f468\u200d\U0001f469\U0001f3fd",
        2,
        "the modifier looks past the joiner to the base",
    ),
]


@pytest.mark.parametrize("text, expected, why", WIDTH_CASES)
def test_display_width(text, expected, why):
    assert wcswidth(text) == expected, why
