# -*- coding: utf-8 -*-
"""
Module: tests/test_ui_language.py
Description: Ratchet — every user-facing string in the TUI is English.
Author: Zev
Date: 2026-10-01
"""

from __future__ import annotations

import io
import re
import tokenize
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1] / "pigit"

#: Anything outside these blocks in a string literal is not English text.
#: Covers CJK ideographs, CJK punctuation and the fullwidth forms — a stray
#: fullwidth comma is just as wrong in a toast as a whole Chinese sentence,
#: and is much easier to miss on review.
NON_ENGLISH = re.compile(r"[　-〿一-鿿＀-￯]")

#: The module header's Description field is the one documented place a
#: non-English description is allowed (CLAUDE.md).
HEADER_FIELD = re.compile(r"^\s*(Module|Description|Author|Date):", re.M)


def _module_header_end(source: str) -> int:
    """Last line of the module docstring, or 0 when there is none."""
    lines = source.splitlines()
    start = next(
        (i for i, l in enumerate(lines[:5]) if l.strip().startswith('"""')), None
    )
    if start is None:
        return 0
    for end in range(start + 1, min(len(lines), 40)):
        if '"""' in lines[end]:
            return end + 1  # 1-based
    return 0


def _offending_literals(path: Path) -> list[tuple[int, str]]:
    source = path.read_text(encoding="utf-8")
    header_end = _module_header_end(source)
    found: list[tuple[int, str]] = []
    for tok in tokenize.generate_tokens(io.StringIO(source).readline):
        if tok.type != tokenize.STRING or not NON_ENGLISH.search(tok.string):
            continue
        row = tok.start[0]
        if row <= header_end and HEADER_FIELD.search(tok.string):
            continue
        found.append((row, tok.string.strip()[:80]))
    return found


def _python_files() -> list[Path]:
    return sorted(ROOT.rglob("*.py"))


def test_no_non_english_string_literals():
    """A Chinese toast among English ones reads as a bug, not a translation.

    Docstrings are exempt: several explain a design decision at length and the
    rule is about what the user sees, not what the code documents. The module
    header's Description field is exempt per CLAUDE.md.
    """
    offenders: list[str] = []
    for path in _python_files():
        for row, text in _offending_literals(path):
            offenders.append(f"{path.relative_to(ROOT.parent)}:{row}  {text}")

    assert not offenders, "non-English string literals:\n" + "\n".join(offenders)


def test_the_scan_actually_looks_at_the_tree():
    """Guards the guard: a bad ROOT or a regex that stopped matching would
    make the test above pass vacuously."""
    files = _python_files()
    assert len(files) > 50

    # And the detector really does fire on the thing it is looking for.
    sample = 'show_toast("未配置 repos.json")'
    hits = [
        tok
        for tok in tokenize.generate_tokens(io.StringIO(sample).readline)
        if tok.type == tokenize.STRING and NON_ENGLISH.search(tok.string)
    ]
    assert len(hits) == 1
