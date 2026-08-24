"""
Module: tests/app/test_diff_content.py
Description: Unit tests for DiffContent structure (parse, plain mode).
Author: Zev
Date: 2026-08-24
"""

from __future__ import annotations

from pigit.diff_content import DiffContent
from pigit.termui.syntax import SyntaxTokenizer


def _simple_diff() -> list[str]:
    return [
        "diff --git a/f.py b/f.py",
        "--- a/f.py",
        "+++ b/f.py",
        "@@ -1,2 +1,2 @@",
        " context",
        "-old hello world",
        "+old new world",
    ]


def test_from_diff_lines_parses_one_hunk() -> None:
    tok = SyntaxTokenizer()
    doc = DiffContent.from_diff_lines(_simple_diff(), word_diff=False, tokenizer=tok)
    assert len(doc.hunks) == 1
    assert doc.hunks[0].start == 3
    assert doc.lines[5].startswith("-")
    assert len(doc.heatmap) == len(doc.lines)
    assert len(doc.line_numbers) == len(doc.lines)


def test_from_diff_lines_word_diff_segments() -> None:
    tok = SyntaxTokenizer()
    doc = DiffContent.from_diff_lines(_simple_diff(), word_diff=True, tokenizer=tok)
    assert doc.word_diff_segments[5]  # deleted line has segments
    assert doc.word_diff_segments[6]  # added line has segments


def test_from_plain_lines_no_hunks() -> None:
    tok = SyntaxTokenizer()
    doc = DiffContent.from_plain_lines(["a = 1", "b = 2"], language="py", tokenizer=tok)
    assert doc.hunks == []
    assert doc.line_numbers == ["   1", "   2"] or len(doc.line_numbers) == 2
    assert doc.heatmap == [" ", " "]


def test_no_git_import() -> None:
    import pigit.diff_content as mod
    import inspect

    src = inspect.getsource(mod)
    assert "pigit.git" not in src
    assert "GitApi" not in src
