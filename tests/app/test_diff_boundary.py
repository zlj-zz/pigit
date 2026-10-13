# -*- coding: utf-8 -*-
"""
Module: tests/app/test_diff_boundary.py
Description: Every diff reader agrees on where one file's block ends.
Author: Zev
Date: 2026-10-08
"""

from __future__ import annotations

from pigit.app_diff import DiffType, DiffViewer
from pigit.diff_content import DiffContent, path_from_diff_line
from pigit.termui.syntax import SyntaxTokenizer


def _combined_diff() -> list[str]:
    """A two-parent merge whose resolution differs from both parents.

    Captured from ``git show HEAD`` on a real evil merge. A combined diff opens
    each file with ``diff --cc <path>`` -- a single path and no ``a/``/``b/``
    prefix, so it matches neither the ``diff --git`` pattern nor the literal.
    """
    return [
        "diff --cc f1.py",
        "index af70335,ac05874..8bcb16a",
        "--- a/f1.py",
        "+++ b/f1.py",
        "@@@ -1,3 -1,3 +1,3 @@@",
        "  a",
        "- MAIN",
        " -FEAT",
        "++RESOLVED",
        "  c",
        "diff --cc f2.py",
        "index bc7ad8e,15ab89c..c2248aa",
        "--- a/f2.py",
        "+++ b/f2.py",
        "@@@ -1,3 -1,3 +1,3 @@@",
        "  x",
        "- MAIN2",
        " -FEAT2",
        "++RESOLVED2",
        "  z",
    ]


class TestTheBoundaryPredicate:
    def test_it_covers_every_form_git_opens_a_file_with(self):
        for line in (
            "diff --git a/f.py b/f.py",
            "diff --cc f1.py",
            "diff --combined f1.py",
        ):
            assert DiffContent.is_file_boundary(line), line

    def test_content_inside_a_hunk_is_not_a_boundary(self):
        for line in (
            "++RESOLVED",
            " -FEAT",
            "- MAIN",
            "  a",
            "@@@ -1,3 -1,3 +1,3 @@@",
            "",
        ):
            assert not DiffContent.is_file_boundary(line), line

    def test_a_content_line_that_looks_like_a_boundary_is_not_one(self):
        """git prefixes every content line, which keeps them off column 0."""
        assert not DiffContent.is_file_boundary(" diff --git a/f.py b/f.py")
        assert not DiffContent.is_file_boundary("+diff --cc f.py")


class TestTheTwoWalksAgree:
    """``diff_line_sides`` and ``_compute_line_numbers`` are one rule -- is this
    a line of a file, or not -- read twice. They drifted: the sides walk closed
    a file on ``diff --git`` while the numbers walk closed it on ``diff --``, so
    a combined diff's second file was a boundary to one and content to the
    other."""

    def test_a_combined_diff_gets_the_same_verdict_from_both(self):
        content = _combined_diff()
        sides = DiffContent.diff_line_sides(content)
        numbers = DiffContent._compute_line_numbers(content)
        numbered = {i for i, n in enumerate(numbers) if n}
        sided = {i for i, s in enumerate(sides) if s != (None, None)}
        assert numbered == sided

    def test_the_headers_of_every_file_take_no_number(self):
        content = _combined_diff()
        numbers = DiffContent._compute_line_numbers(content)
        headers = [
            i
            for i, line in enumerate(content)
            if DiffContent.is_file_boundary(line)
            or line.startswith(("index ", "--- ", "+++ "))
        ]
        assert len(headers) == 8
        assert [numbers[i] for i in headers] == [""] * len(headers)


class TestHunksDoNotCrossFiles:
    def test_each_combined_file_is_its_own_hunk(self):
        content = _combined_diff()
        hunks = DiffContent._parse_hunks(content)
        assert [(h.start, h.end) for h in hunks] == [(4, 10), (14, 20)]
        assert content[hunks[0].end] == "diff --cc f2.py"


class TestPathFromBoundaryLine:
    def test_a_combined_line_names_its_path_directly(self):
        assert path_from_diff_line("diff --cc f1.py") == "f1.py"
        assert path_from_diff_line("diff --combined dir/f1.py") == "dir/f1.py"

    def test_a_quoted_combined_path_loses_its_quotes(self):
        assert path_from_diff_line('diff --cc "my file.py"') == "my file.py"

    def test_the_two_path_form_still_resolves_both_sides(self):
        assert path_from_diff_line("diff --git a/f.py b/f.py") == "f.py"
        assert path_from_diff_line("diff --git a/gone.py b/dev/null") == "gone.py"
        assert path_from_diff_line("diff --git a/dev/null b/new.py") == "new.py"

    def test_a_content_line_yields_nothing(self):
        assert path_from_diff_line("++RESOLVED") == ""


class TestALanguageIsStillDetected:
    def test_combined_content_follows_its_file_path(self):
        content = _combined_diff()
        langs = DiffContent._detect_line_languages(content, SyntaxTokenizer())
        assert langs[5] == "py"
        assert langs[15] == "py"

    def test_the_combined_form_reads_exactly_like_the_two_path_form(self):
        """The boundary line must hand over the path in both forms; otherwise
        every line up to the ``+++`` header keeps the previous file's language.
        """
        tokenizer = SyntaxTokenizer()
        combined = _combined_diff()[:4]
        two_path = [
            "diff --git a/f1.py b/f1.py",
            "index af70335,ac05874..8bcb16a",
            "--- a/f1.py",
            "+++ b/f1.py",
        ]
        assert DiffContent._detect_line_languages(
            combined, tokenizer
        ) == DiffContent._detect_line_languages(two_path, tokenizer)


class TestTheFileNavListsEveryFile:
    def test_a_combined_diff_lists_both_files(self):
        dv = DiffViewer()
        dv.set_diff_type(DiffType.COMMIT)
        dv.set_content(_combined_diff())
        assert [s.path for s in dv._file_sections] == ["f1.py", "f2.py"]


class TestTheFallbackScan:
    def test_a_combined_boundary_ends_the_previous_file(self):
        """The fallback scan runs when no file source is available. Without the
        reset an open triple quote in one file swallows the next file's code."""
        lines = ["+s = '''", "diff --cc f.py", "+a = 1"]
        mask = SyntaxTokenizer.compute_multiline_mask(
            lines, ["py"] * len(lines), strip_diff_prefix=True
        )
        assert mask == ["docstring", None, None]
