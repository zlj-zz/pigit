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


# --- Line numbers -----------------------------------------------------------
#
# A line is numbered only when it is a line of a file, which means it lies
# inside a hunk. Everything else a diff stream carries -- the `git show`
# preamble, a file's extended headers, the hunk header -- is metadata.
#
# The fixtures below are the shapes git actually emits, captured from a real
# repository: `git show`, `git stash show -p` and `git diff`.


def _commit_diff() -> list[str]:
    """`git show`: a commit subject block, then the patch."""
    return [
        "commit e7f2a88883c3aea0d569d4ff3ac199a0a47ce92f",
        "Author: Zev <zev@example.com>",
        "Date:   Thu Oct 8 16:33:01 2026 +0800",
        "",
        "    tidy the parser",
        "",
        "diff --git a/src/app.py b/src/app.py",
        "index a5dc0f4..6f72822 100644",
        "--- a/src/app.py",
        "+++ b/src/app.py",
        "@@ -10,3 +20,4 @@ from .parser import parse",
        " line three",
        "-old line four",
        "+new line four",
        "+added line",
    ]


def _stash_diff() -> list[str]:
    """`git stash show -p`: no preamble, straight into the patch."""
    return [
        "diff --git a/README.md b/README.md",
        "index e6e700a..404498f 100644",
        "--- a/README.md",
        "+++ b/README.md",
        "@@ -1,2 +1,3 @@",
        " first",
        "+second",
    ]


def _numbers(lines: list[str]) -> list[str]:
    return DiffContent._compute_line_numbers(lines)


class TestLineNumbersOnlyCountFileLines:

    def test_the_commit_preamble_takes_no_number(self):
        """It read 0,1,2,... through the subject before, then restarted at the
        hunk's own first line -- two unrelated sequences in one column."""
        numbers = _numbers(_commit_diff())
        assert numbers[:6] == [""] * 6

    def test_a_files_extended_headers_take_no_number(self):
        """`diff --git`, `index`, `new file mode` and friends all fell through
        to the context branch and were numbered."""
        numbers = _numbers(_commit_diff())
        assert numbers[6:10] == ["", "", "", ""]  # diff --git, index, ---, +++

    def test_the_hunk_header_takes_no_number(self):
        assert _numbers(_commit_diff())[10] == ""

    def test_a_hunks_own_lines_carry_its_numbering(self):
        """The hunk starts at old 10 / new 20, so the two sides are told apart:
        context advances both, a deletion reports the old line it removes, an
        addition the new line it adds. Starting them at the same number would
        hide a deletion reading the wrong counter."""
        numbers = _numbers(_commit_diff())
        assert numbers[11:] == ["  20", "  11", "  21", "  22"]

    def test_a_stash_diff_is_unaffected(self):
        """It never had a preamble, but its `index` line was numbered all the
        same -- every diff type carries those headers."""
        numbers = _numbers(_stash_diff())
        assert numbers[:4] == ["", "", "", ""]
        assert numbers[4:] == ["", "   1", "   2"]

    def test_every_file_starts_over_rather_than_continuing(self):
        """The old code kept incrementing across the file boundary, so the
        second file's `index` line was numbered while the first file's content
        was too."""
        lines = _stash_diff() + [
            "diff --git a/b.py b/b.py",
            "index 0000000..fb188b9 100644",
            "new file mode 100644",
            "--- /dev/null",
            "+++ b/b.py",
            "@@ -0,0 +1 @@",
            "+scratched",
        ]
        numbers = _numbers(lines)
        assert numbers[7:12] == ["", "", "", "", ""]  # every header, blank
        assert numbers[12] == ""  # the new file's hunk header
        assert numbers[13] == "   1"  # and its content starts over at 1

    def test_a_binary_file_takes_no_number(self):
        numbers = _numbers(
            [
                "diff --git a/blob.bin b/blob.bin",
                "new file mode 100644",
                "index 0000000..b43761b",
                "Binary files /dev/null and b/blob.bin differ",
            ]
        )
        assert numbers == [""] * 4

    def test_a_no_newline_marker_takes_no_number(self):
        numbers = _numbers(
            [
                "diff --git a/f.py b/f.py",
                "@@ -1 +1 @@",
                "-old",
                "\\ No newline at end of file",
                "+new",
            ]
        )
        assert numbers == ["", "", "   1", "", "   1"]

    def test_one_entry_per_line(self):
        for lines in (_commit_diff(), _stash_diff()):
            assert len(_numbers(lines)) == len(lines)


class TestCombinedMergeDiffsKeepTheirOldNumbers:
    """`@@@` satisfies `startswith("@@")` but not the hunk regex, so the
    counters reset to zero -- and the combined diff's lines were numbered from
    there. That is what happens today; this pins it rather than changing it,
    because fixing `--cc` is a separate job."""

    def test_a_combined_hunk_numbers_from_zero(self):
        numbers = _numbers(
            [
                "diff --cc x.py",
                "@@@ -1,2 -1,2 +1,3 @@@",
                "  common",
                " +ours",
                "++theirs",
            ]
        )
        assert numbers == ["", "", "   0", "   1", "   2"]

    def test_the_preamble_is_still_excluded(self):
        """The one thing the combined path does get right: `diff --cc` ends
        the previous file, matched by prefix rather than by DIFF_GIT_RE."""
        numbers = _numbers(
            [
                "commit abc1234",
                "    subject",
                "diff --git a/a.py b/a.py",
                "@@ -1 +1 @@",
                "-a",
                "+b",
                "diff --cc c.py",
                "@@@ -1,1 -1,1 +1,1 @@@",
                "  x",
            ]
        )
        assert numbers[:2] == ["", ""]
        assert numbers[5] == "   1"  # a.py's hunk still numbered
        assert numbers[6] == ""  # the `diff --cc` boundary


def test_from_plain_lines_still_numbers_sequentially() -> None:
    """File History does not go through the hunk walk at all -- it numbers
    every line 1..n, and must keep doing so."""
    doc = DiffContent.from_plain_lines(
        ["a = 1", "b = 2", "c = 3"], language="py", tokenizer=SyntaxTokenizer()
    )
    assert doc.line_numbers == ["   1", "   2", "   3"]
